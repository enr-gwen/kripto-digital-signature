import io

import pytest
from reportlab.pdfgen import canvas

from app import keys


def _make_pdf(text="Surat Keterangan Kegiatan", pages=2) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595.27, 841.89), pageCompression=0)
    for i in range(pages):
        c.drawString(72, 760, f"{text} - halaman {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def sample_pdf():
    return _make_pdf()


@pytest.fixture
def make_pdf():
    return _make_pdf


@pytest.fixture(scope="session")
def private_key():
    return keys.generate_keypair()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"
