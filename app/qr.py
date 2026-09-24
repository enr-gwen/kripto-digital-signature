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

DOC_ID_RE = re.compile(r"^[0-9a-f]{16}$")


def build_payload(doc_id, nama, jabatan, tanggal, institusi, base_url) -> dict:
    return {
        "v": 1,
        "doc_id": doc_id,
        "nama": nama,
        "jabatan": jabatan,
        "tanggal": tanggal,
        "institusi": institusi,
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
    """Baca QR dari gambar PIL. Kembalikan teks atau None."""
    rgb = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    detector = cv2.QRCodeDetector()
    text, _, _ = detector.detectAndDecode(bgr)
    if text:
        return text
    # Cadangan: perbesar 2x lalu coba lagi (QR kecil di halaman besar).
    big = cv2.resize(bgr, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    text, _, _ = detector.detectAndDecode(big)
    return text or None


def decode_qr_from_pdf(pdf_bytes: bytes, dpi: int = 200):
    """Render tiap halaman (dari belakang) lalu cari QR. Kembalikan payload
    (dict tervalidasi) atau None bila tidak ada QR yang terbaca."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None
    try:
        for index in range(len(doc) - 1, -1, -1):
            pix = doc[index].get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            payload = parse_payload(decode_qr_image(img))
            if payload:
                return payload
    except Exception:
        return None
    finally:
        doc.close()
    return None
