import pytest

from app import keys, qr, service
from app.pdf_stamp import stamp_qr

DATA = dict(nama="Budi Santoso", jabatan="Ketua Panitia",
            institusi="Universitas Siliwangi")


@pytest.fixture
def signed(sample_pdf, private_key, db_path):
    pdf, doc_id = service.sign_document(
        sample_pdf, private_key=private_key, db_path=db_path,
        tanggal="2026-09-24", **DATA)
    return pdf, doc_id


def _verify(pdf, private_key, db_path, **kw):
    return service.verify_document(
        pdf, public_key=private_key.public_key(), db_path=db_path, **kw)


def test_alur_lengkap_sign_lalu_verify_valid(signed, private_key, db_path):
    pdf, doc_id = signed
    hasil = _verify(pdf, private_key, db_path)
    assert hasil.valid and hasil.status == "VALID"
    assert hasil.metadata["doc_id"] == doc_id
    assert hasil.metadata["nama"] == DATA["nama"]


def test_tamper_satu_byte_ditolak(signed, private_key, db_path):
    pdf, doc_id = signed
    diubah = bytearray(pdf)
    diubah[len(diubah) // 2] ^= 0x01
    hasil = _verify(bytes(diubah), private_key, db_path, doc_id=doc_id)
    assert not hasil.valid and hasil.status == "DOKUMEN_DIUBAH"


def test_tambah_byte_di_akhir_ditolak(signed, private_key, db_path):
    pdf, _ = signed
    hasil = _verify(pdf + b"\n", private_key, db_path)
    assert not hasil.valid and hasil.status == "DOKUMEN_DIUBAH"


def test_kunci_publik_salah_ditolak(signed, db_path):
    pdf, _ = signed
    kunci_lain = keys.generate_keypair()
    hasil = service.verify_document(
        pdf, public_key=kunci_lain.public_key(), db_path=db_path)
    assert not hasil.valid and hasil.status == "KUNCI_TIDAK_COCOK"


def test_qr_palsu_doc_id_tidak_dikenal(sample_pdf, private_key, db_path):
    palsu = qr.build_payload("ffffffffffffffff", "Penipu", "Direktur",
                             "2026-09-24", "Universitas Siliwangi",
                             "http://localhost:8501")
    img = qr.make_qr_image(qr.payload_to_text(palsu))
    pdf_palsu = stamp_qr(sample_pdf, img, ["Palsu"])
    hasil = _verify(pdf_palsu, private_key, db_path)
    assert not hasil.valid and hasil.status == "DOC_ID_TIDAK_DIKENAL"


def test_qr_asli_ditempel_ke_dokumen_lain_ditolak(
        signed, make_pdf, private_key, db_path):
    _, doc_id = signed
    payload = qr.build_payload(doc_id, DATA["nama"], DATA["jabatan"],
                               "2026-09-24", DATA["institusi"],
                               "http://localhost:8501")
    img = qr.make_qr_image(qr.payload_to_text(payload))
    dokumen_lain = stamp_qr(make_pdf("Dokumen berbeda"), img, ["Salinan"])
    hasil = _verify(dokumen_lain, private_key, db_path)
    assert not hasil.valid and hasil.status == "DOKUMEN_DIUBAH"


def test_pdf_tanpa_qr_tidak_terbaca(sample_pdf, private_key, db_path):
    hasil = _verify(sample_pdf, private_key, db_path)
    assert not hasil.valid and hasil.status == "QR_TIDAK_TERBACA"
