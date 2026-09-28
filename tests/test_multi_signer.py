"""Uji fitur pengayaan: multi-signer sekuensial (mis. Ketua lalu Dekan)."""
import pytest

from app import keys, service

KETUA = dict(nama="Budi Santoso", jabatan="Ketua Panitia",
            institusi="Universitas Siliwangi")
DEKAN = dict(nama="Prof. Siti Aminah", jabatan="Dekan",
            institusi="Universitas Siliwangi")


@pytest.fixture
def kunci_kedua():
    return keys.generate_keypair()


@pytest.fixture
def dokumen_2_tanda_tangan(sample_pdf, private_key, kunci_kedua, db_path):
    """Ketua menandatangani dulu, lalu Dekan menandatangani hasilnya."""
    pdf_1, doc_id_1 = service.sign_document(
        sample_pdf, private_key=private_key, db_path=db_path,
        tanggal="2026-09-24", **KETUA)
    pdf_2, doc_id_2 = service.sign_document(
        pdf_1, private_key=kunci_kedua, db_path=db_path,
        tanggal="2026-09-25", parent_doc_id=doc_id_1, **DEKAN)
    return pdf_2, doc_id_1, doc_id_2


def test_urutan_tersimpan_benar(dokumen_2_tanda_tangan, db_path):
    from app import storage
    _, doc_id_1, doc_id_2 = dokumen_2_tanda_tangan
    assert storage.get_document(db_path, doc_id_1)["urutan"] == 1
    assert storage.get_document(db_path, doc_id_2)["urutan"] == 2
    assert storage.get_document(db_path, doc_id_2)["parent_doc_id"] == doc_id_1


def test_verifikasi_dokumen_2_tanda_tangan_valid(
        dokumen_2_tanda_tangan, kunci_kedua, db_path):
    pdf_akhir, _, _ = dokumen_2_tanda_tangan
    hasil = service.verify_document(
        pdf_akhir, public_key=kunci_kedua.public_key(), db_path=db_path)
    assert hasil.valid and hasil.status == "VALID"
    assert hasil.metadata["nama"] == DEKAN["nama"]  # penandatangan TERAKHIR
    assert hasil.metadata["urutan"] == 2


def test_riwayat_berisi_kedua_penandatangan_berurutan(
        dokumen_2_tanda_tangan, kunci_kedua, db_path):
    pdf_akhir, doc_id_1, doc_id_2 = dokumen_2_tanda_tangan
    hasil = service.verify_document(
        pdf_akhir, public_key=kunci_kedua.public_key(), db_path=db_path)
    assert [r["doc_id"] for r in hasil.riwayat] == [doc_id_1, doc_id_2]
    assert [r["nama"] for r in hasil.riwayat] == [KETUA["nama"], DEKAN["nama"]]


def test_verifikasi_dengan_kunci_penandatangan_pertama_gagal(
        dokumen_2_tanda_tangan, private_key, db_path):
    """Kunci Ketua tidak bisa memverifikasi tanda tangan akhir milik Dekan."""
    pdf_akhir, _, _ = dokumen_2_tanda_tangan
    hasil = service.verify_document(
        pdf_akhir, public_key=private_key.public_key(), db_path=db_path)
    assert not hasil.valid and hasil.status == "KUNCI_TIDAK_COCOK"


def test_tamper_setelah_tanda_tangan_kedua_ditolak(
        dokumen_2_tanda_tangan, kunci_kedua, db_path):
    pdf_akhir, _, _ = dokumen_2_tanda_tangan
    rusak = bytearray(pdf_akhir)
    rusak[len(rusak) // 2] ^= 0x01
    hasil = service.verify_document(
        bytes(rusak), public_key=kunci_kedua.public_key(), db_path=db_path)
    assert not hasil.valid and hasil.status in ("DOKUMEN_DIUBAH", "QR_TIDAK_TERBACA")


def test_dokumen_setelah_tanda_tangan_pertama_saja_tetap_valid_sendiri(
        sample_pdf, private_key, db_path):
    """Sebelum Dekan menandatangani, hasil tanda tangan Ketua tetap sah berdiri
    sendiri (multi-signer bersifat opsional/bertahap, bukan wajib 2 tahap)."""
    pdf_1, doc_id_1 = service.sign_document(
        sample_pdf, private_key=private_key, db_path=db_path, **KETUA)
    hasil = service.verify_document(
        pdf_1, public_key=private_key.public_key(), db_path=db_path)
    assert hasil.valid and len(hasil.riwayat) == 1


def test_parent_doc_id_tidak_ada_menolak_dengan_jelas(
        sample_pdf, private_key, db_path):
    with pytest.raises(ValueError):
        service.sign_document(
            sample_pdf, private_key=private_key, db_path=db_path,
            parent_doc_id="tidak-ada-di-db", **KETUA)


def test_tiga_penandatangan_berurutan(sample_pdf, db_path):
    """Rantai lebih panjang: Staf -> Ketua -> Dekan, 3 tanda tangan sekaligus."""
    kunci = [keys.generate_keypair() for _ in range(3)]
    peran = [dict(nama="Andi", jabatan="Staf", institusi="Universitas Siliwangi"),
             dict(nama="Budi", jabatan="Ketua", institusi="Universitas Siliwangi"),
             dict(nama="Prof. Siti", jabatan="Dekan", institusi="Universitas Siliwangi")]
    pdf = sample_pdf
    parent = None
    for k, p in zip(kunci, peran):
        pdf, doc_id = service.sign_document(
            pdf, private_key=k, db_path=db_path, parent_doc_id=parent, **p)
        parent = doc_id

    hasil = service.verify_document(
        pdf, public_key=kunci[-1].public_key(), db_path=db_path)
    assert hasil.valid
    assert len(hasil.riwayat) == 3
    assert [r["jabatan"] for r in hasil.riwayat] == ["Staf", "Ketua", "Dekan"]
