"""Menempelkan QR-Code + keterangan ke halaman terakhir PDF."""
import io

from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

CM = 28.3465  # poin per cm


def _latin1(text: str) -> str:
    """Font bawaan PDF hanya mendukung Latin-1; karakter lain diganti '?'."""
    return text.encode("latin-1", "replace").decode("latin-1")


def stamp_qr(pdf_bytes: bytes, qr_image, caption_lines,
             size_cm: float = 3.0, margin_cm: float = 1.5) -> bytes:
    """Kembalikan bytes PDF baru dengan QR di pojok kanan bawah halaman terakhir.

    PENTING: bytes hasil fungsi ini yang di-hash dan ditandatangani, dan file
    itu tidak boleh disimpan ulang (re-save) oleh program lain, karena byte-nya
    akan berubah dan verifikasi gagal.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    last = reader.pages[-1]
    width = float(last.mediabox.width)
    height = float(last.mediabox.height)

    size = size_cm * CM
    margin = margin_cm * CM
    x = width - margin - size
    y = margin

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