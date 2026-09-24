import pytest

from app import keys, signer

PASS = b"passphrase-untuk-test"
DOC = b"%PDF-1.4 isi dokumen contoh untuk diuji"


@pytest.fixture(scope="module")
def keypair():
    return keys.generate_keypair()


def test_sign_dan_verify_valid(keypair):
    digest = signer.hash_bytes(DOC)
    sig = signer.sign_digest(keypair, digest)
    assert signer.verify_digest(keypair.public_key(), digest, sig) is True


def test_tamper_satu_byte_verifikasi_gagal(keypair):
    sig = signer.sign_digest(keypair, signer.hash_bytes(DOC))
    dokumen_diubah = bytearray(DOC)
    dokumen_diubah[10] ^= 0x01  # ubah 1 bit pada 1 byte
    digest_baru = signer.hash_bytes(bytes(dokumen_diubah))
    assert signer.verify_digest(keypair.public_key(), digest_baru, sig) is False


def test_kunci_publik_salah_verifikasi_gagal(keypair):
    kunci_lain = keys.generate_keypair()
    digest = signer.hash_bytes(DOC)
    sig = signer.sign_digest(keypair, digest)
    assert signer.verify_digest(kunci_lain.public_key(), digest, sig) is False


def test_signature_dirusak_verifikasi_gagal(keypair):
    digest = signer.hash_bytes(DOC)
    sig = bytearray(signer.sign_digest(keypair, digest))
    sig[-1] ^= 0xFF
    assert signer.verify_digest(keypair.public_key(), digest, bytes(sig)) is False


def test_private_key_tersimpan_terenkripsi(keypair):
    pem = keys.private_key_to_pem(keypair, PASS)
    assert b"ENCRYPTED PRIVATE KEY" in pem


def test_passphrase_salah_gagal_memuat_private_key(keypair):
    pem = keys.private_key_to_pem(keypair, PASS)
    with pytest.raises(ValueError):
        keys.load_private_key(pem, b"passphrase-salah")


def test_roundtrip_simpan_dan_muat_kunci(tmp_path):
    priv, pub = keys.save_keypair(tmp_path, "penandatangan", PASS)
    private_key = keys.load_private_key(priv.read_bytes(), PASS)
    public_key = keys.load_public_key(pub.read_bytes())
    digest = signer.hash_bytes(DOC)
    sig = signer.sign_digest(private_key, digest)
    assert signer.verify_digest(public_key, digest, sig)


def test_digest_bukan_32_byte_ditolak(keypair):
    with pytest.raises(ValueError):
        signer.sign_digest(keypair, b"terlalu-pendek")
