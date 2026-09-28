"""Pembuatan dan pembacaan QR-Code.

Isi QR = doc_id + metadata + URL verifikasi. Tanda tangan TIDAK ada di QR
(disimpan di database), karena QR ikut ter-hash bersama PDF.
"""
import io
import json
import re

import cv2
import numpy as np
import pymupdf
import qrcode
from PIL import Image

try:
    from pyzbar.pyzbar import decode as _zbar_decode
    _ADA_ZBAR = True
except Exception:  # pustaka/library sistem zbar tidak terpasang
    _ADA_ZBAR = False

DOC_ID_RE = re.compile(r"^[0-9a-f]{16}$")


def build_payload(doc_id, nama, jabatan, tanggal, institusi, base_url,
                  urutan: int = 1) -> dict:
    return {
        "v": 1,
        "doc_id": doc_id,
        "nama": nama,
        "jabatan": jabatan,
        "tanggal": tanggal,
        "institusi": institusi,
        "urutan": urutan,
        "url": f"{base_url.rstrip('/')}/?doc_id={doc_id}",
    }


def payload_to_text(payload: dict) -> str:
    """JSON kanonik (urutan kunci tetap, tanpa spasi)."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True,
                      ensure_ascii=False)


def parse_payload(text):
    """Validasi teks hasil scan QR. Kembalikan dict atau None bila tidak sah."""
    if not text:
        return None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    doc_id = data.get("doc_id")
    if not isinstance(doc_id, str) or not DOC_ID_RE.match(doc_id):
        return None
    return data


def make_qr_image(text: str) -> Image.Image:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(text)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def decode_qr_image(img: Image.Image):
    """Baca SATU QR dari gambar PIL. Kembalikan teks atau None.

    Memakai pyzbar (via libzbar) bila tersedia karena jauh lebih andal;
    OpenCV dipakai sebagai cadangan otomatis bila pyzbar tidak terpasang.
    """
    if _ADA_ZBAR:
        try:
            hasil = _zbar_decode(img)
        except Exception:
            hasil = []
        if hasil:
            return hasil[0].data.decode("utf-8", "replace")

    rgb = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    detector = cv2.QRCodeDetector()
    for kandidat in (bgr, cv2.resize(bgr, None, fx=2, fy=2,
                                     interpolation=cv2.INTER_CUBIC)):
        try:
            text, _, _ = detector.detectAndDecode(kandidat)
        except cv2.error:
            text = ""
        if text:
            return text
    return None


def decode_qr_from_pdf(pdf_bytes: bytes, dpi: int = 200):
    """Render tiap halaman (dari belakang) lalu cari QR. Kembalikan payload
    (dict tervalidasi) PERTAMA yang terbaca, atau None. Untuk dokumen
    multi-signer (>1 QR di halaman yang sama), pakai decode_all_qr_from_pdf."""
    semua = decode_all_qr_from_pdf(pdf_bytes, dpi=dpi)
    return semua[0] if semua else None


def _decode_multi_image(img: Image.Image):
    """Baca SEMUA QR pada satu gambar. Kembalikan list teks (bisa kosong).

    Memakai pyzbar dulu (mendeteksi banyak QR sekaligus dengan andal); kalau
    tidak tersedia, baru jatuh ke kombinasi OpenCV (detectAndDecodeMulti +
    detectAndDecode) yang kurang stabil untuk beberapa QR berdekatan.
    """
    if _ADA_ZBAR:
        try:
            hasil = _zbar_decode(img)
        except Exception:
            hasil = []
        if hasil:
            return [h.data.decode("utf-8", "replace") for h in hasil]

    rgb = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    detector = cv2.QRCodeDetector()
    hasil = set()

    for candidate in (bgr, cv2.resize(bgr, None, fx=2, fy=2,
                                      interpolation=cv2.INTER_CUBIC)):
        try:
            ok, decoded, *_ = detector.detectAndDecodeMulti(candidate)
        except cv2.error:
            ok, decoded = False, []
        if ok:
            hasil.update(t for t in decoded if t)
        try:
            teks, *_ = detector.detectAndDecode(candidate)
        except cv2.error:
            teks = ""
        if teks:
            hasil.add(teks)
        if hasil:
            break
    return list(hasil)


def _baca_lewat_crop_slot(page, dpi: int):
    """Baca QR satu-per-satu lewat crop presisi di posisi tiap `slot` yang
    KITA sendiri tentukan saat menempel (lihat pdf_stamp.geometri_slot).

    Jauh lebih andal daripada mendeteksi beberapa QR sekaligus dalam satu
    gambar besar (OpenCV sering hanya menemukan sebagian bila QR berdekatan),
    karena tiap crop hanya berisi SATU QR tanpa gangguan QR tetangganya.
    """
    from .pdf_stamp import geometri_slot  # import lokal: hindari siklus impor

    width_pt, height_pt = page.rect.width, page.rect.height
    scale = dpi / 72.0
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    pad_pt = 0.4 * 28.3465  # ~0.4 cm, ruang aman tanpa menyentuh stempel lain

    hasil, gagal_beruntun = [], 0
    for slot in range(0, 12):
        x, y, size = geometri_slot(width_pt, height_pt, slot)
        if y + size > height_pt:  # sudah melewati batas atas halaman
            break
        kiri = max(0, int((x - pad_pt) * scale))
        kanan = min(pix.width, int((x + size + pad_pt) * scale))
        atas = max(0, int((height_pt - (y + size) - pad_pt) * scale))
        bawah = min(pix.height, int((height_pt - y + pad_pt) * scale))
        crop = img.crop((kiri, atas, kanan, bawah))
        payload = parse_payload(decode_qr_image(crop))
        if payload:
            hasil.append(payload)
            gagal_beruntun = 0
        else:
            gagal_beruntun += 1
            if gagal_beruntun >= 2:  # 2x kosong berturut-turut: anggap habis
                break
    return hasil


def decode_all_qr_from_pdf(pdf_bytes: bytes, dpi: int = 250):
    """Render halaman terakhir yang mengandung QR, kembalikan SEMUA payload
    valid yang ditemukan (diurutkan dari 'urutan' terkecil ke terbesar).
    Berguna untuk dokumen multi-signer dengan beberapa QR di satu halaman.
    """
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return []
    try:
        for index in range(len(doc) - 1, -1, -1):
            page = doc[index]

            # Cara utama: crop presisi per-slot (andal untuk stempel kita sendiri).
            payloads = _baca_lewat_crop_slot(page, dpi)

            # Cadangan: deteksi umum di seluruh halaman (mis. format/skala
            # berbeda dari dugaan geometri_slot).
            if not payloads:
                for coba_dpi in (dpi, 300, 150):
                    pix = page.get_pixmap(dpi=coba_dpi)
                    img = Image.frombytes("RGB", (pix.width, pix.height),
                                          pix.samples)
                    ditemukan = [parse_payload(t) for t in
                                _decode_multi_image(img)]
                    payloads = [p for p in ditemukan if p]
                    if payloads:
                        break

            if payloads:
                unik = {p["doc_id"]: p for p in payloads}  # buang duplikat
                return sorted(unik.values(), key=lambda p: p.get("urutan", 1))
    except Exception:
        return []
    finally:
        doc.close()
    return []
