"""Menempelkan QR-Code + keterangan ke halaman terakhir PDF."""
import io

from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

CM = 28.3465  # poin per cm
UKURAN_QR_CM = 3.0
MARGIN_CM = 1.5
JARAK_ANTAR_STEMPEL_CM = UKURAN_QR_CM + 1.2  # tinggi + jarak antar-stempel
MAX_SLOT = 12  # batas wajar jumlah penandatangan berurutan


def geometri_slot(width_pt: float, height_pt: float, slot: int,
                  size_cm: float = UKURAN_QR_CM, margin_cm: float = MARGIN_CM):
    """Kembalikan (x, y, size) dalam poin PDF untuk kotak QR pada `slot`
    tertentu (0 = penandatangan pertama/paling bawah). Dipakai bersama oleh
    stamp_qr() (menempel) dan app.qr (membaca ulang lewat crop presisi), agar
    keduanya selalu sepakat soal posisi setiap stempel."""
    size = size_cm * CM
    margin = margin_cm * CM
    jarak = size + 1.2 * CM
    x = width_pt - margin - size
    y = margin + slot * jarak
    return x, y, size


def _latin1(text: str) -> str:
    """Font bawaan PDF hanya mendukung Latin-1; karakter lain diganti '?'."""
    return text.encode("latin-1", "replace").decode("latin-1")


def stamp_qr(pdf_bytes: bytes, qr_image, caption_lines,
             size_cm: float = 3.0, margin_cm: float = 1.5, slot: int = 0) -> bytes:
    """Kembalikan bytes PDF baru dengan QR di pojok kanan bawah halaman terakhir.

    `slot` (0, 1, 2, ...) menumpuk stempel ke ATAS agar tanda tangan multi-signer
    tidak saling menimpa: slot 0 = penandatangan pertama (paling bawah),
    slot 1 = penandatangan kedua (di atasnya), dan seterusnya.

    PENTING: bytes hasil fungsi ini yang di-hash dan ditandatangani, dan file
    itu tidak boleh disimpan ulang (re-save) oleh program lain, karena byte-nya
    akan berubah dan verifikasi gagal.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    last = reader.pages[-1]
    width = float(last.mediabox.width)
    height = float(last.mediabox.height)

    x, y, size = geometri_slot(width, height, slot, size_cm, margin_cm)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height), pageCompression=0)
    png = io.BytesIO()
    qr_image.save(png, format="PNG")
    png.seek(0)
    c.drawImage(ImageReader(png), x, y, size, size)
    c.setFont("Helvetica", 7)
    text_y = y + size - 8
    for line in caption_lines:
        c.drawRightString(x - 6, text_y, _latin1(line))
        text_y -= 9
    c.save()
    buf.seek(0)

    # Salin dokumen ke writer DULU, baru gabungkan overlay di halaman milik
    # writer (cara yang didukung pypdf; menghindari DeprecationWarning).
    writer = PdfWriter(clone_from=reader)
    writer.pages[-1].merge_page(PdfReader(buf).pages[0])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
