"""Hash SHA-256, tanda tangan ECDSA, dan verifikasi.

Sesuai spesifikasi tugas: tanda tangan dibuat atas NILAI HASH SHA-256 dari
berkas (bukan atas berkas mentah).
"""
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


def hash_bytes(data: bytes) -> bytes:
    """SHA-256 dari data (32 byte)."""
    return hashlib.sha256(data).digest()


def hash_file(path, chunk_size: int = 1024 * 1024) -> bytes:
    """SHA-256 dari berkas, dibaca bertahap agar hemat memori."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.digest()


def sign_digest(private_key, digest: bytes) -> bytes:
    """Tanda tangan ECDSA atas digest SHA-256 (hasil format DER)."""
    if len(digest) != 32:
        raise ValueError("digest harus 32 byte (SHA-256)")
    return private_key.sign(digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))


def verify_digest(public_key, digest: bytes, signature: bytes) -> bool:
    """True bila tanda tangan valid, False bila tidak (tidak melempar error)."""
    try:
        public_key.verify(
            signature, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256()))
        )
        return True
    except (InvalidSignature, ValueError):
        return False
