from app import qr
from app.pdf_stamp import stamp_qr


def _payload():
    return qr.build_payload("a3f9c1d27b4e0011", "Budi", "Ketua", "2026-09-24",
                            "Universitas Siliwangi", "http://localhost:8501")


def test_payload_roundtrip_lewat_qr_image():
    teks = qr.payload_to_text(_payload())
    hasil = qr.parse_payload(qr.decode_qr_image(qr.make_qr_image(teks)))
    assert hasil == _payload()


def test_parse_payload_menolak_sampah():
    assert qr.parse_payload("bukan json") is None
    assert qr.parse_payload('{"doc_id": "../../etc/passwd"}') is None
    assert qr.parse_payload("[1,2,3]") is None
    assert qr.parse_payload(None) is None


def test_qr_terbaca_dari_pdf_yang_sudah_distempel(sample_pdf):
    img = qr.make_qr_image(qr.payload_to_text(_payload()))
    stamped = stamp_qr(sample_pdf, img, ["Ditandatangani", "Budi"])
    assert qr.decode_qr_from_pdf(stamped) == _payload()


def test_pdf_tanpa_qr_mengembalikan_none(sample_pdf):
    assert qr.decode_qr_from_pdf(sample_pdf) is None
    assert qr.decode_qr_from_pdf(b"bukan pdf sama sekali") is None
