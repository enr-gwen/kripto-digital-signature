"""Manajemen kunci ECDSA P-256.

Private key disimpan terenkripsi (PKCS#8 + passphrase). Passphrase TIDAK
ditulis di kode: ambil dari environment variable KEY_PASSPHRASE (file .env).
"""
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

try:  # python-dotenv opsional saat testing
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_passphrase() -> bytes:
    """Ambil passphrase dari environment (.env). Gagal keras bila kosong."""
    value = os.environ.get("KEY_PASSPHRASE")
    if not value:
        raise RuntimeError(
            "KEY_PASSPHRASE belum di-set. Salin .env.example ke .env lalu isi."
        )
    return value.encode("utf-8")


def generate_keypair() -> ec.EllipticCurvePrivateKey:
    """Bangkitkan private key ECDSA P-256 (RNG aman dari OS)."""
    return ec.generate_private_key(ec.SECP256R1())


def private_key_to_pem(private_key, passphrase: bytes) -> bytes:
    """Serialisasi private key ke PEM TERENKRIPSI."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase),
    )


def public_key_to_pem(private_key) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def load_private_key(pem: bytes, passphrase: bytes):
    """Muat private key. Melempar ValueError bila passphrase salah."""
    return serialization.load_pem_private_key(pem, password=passphrase)


def load_public_key(pem: bytes):
    return serialization.load_pem_public_key(pem)


def save_keypair(directory, name: str, passphrase: bytes):
    """Buat key pair baru dan simpan ke <directory>/<name>.key & .pub.

    File private key diberi izin 0600 (hanya pemilik yang bisa baca).
    Mengembalikan (path_private, path_public).
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    priv_path = directory / f"{name}.key"
    pub_path = directory / f"{name}.pub"
    if priv_path.exists():
        raise FileExistsError(f"{priv_path} sudah ada; tidak ditimpa.")

    key = generate_keypair()
    priv_path.write_bytes(private_key_to_pem(key, passphrase))
    os.chmod(priv_path, 0o600)
    pub_path.write_bytes(public_key_to_pem(key))
    return priv_path, pub_path
