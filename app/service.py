"""Alur utama: sign_document() dan verify_document().

UI hanya perlu memanggil dua fungsi ini.
"""
import secrets
from dataclasses import dataclass, field
from datetime import date

from . import qr, storage
from .pdf_stamp import stamp_qr
from .signer import hash_bytes, sign_digest, verify_digest

FIELDS_DICEK = ("nama", "jabatan", "tanggal", "institusi")


@dataclass
class VerifyResult:
    valid: bool
    status: str
    message: str
    metadata: dict = field(default_factory=dict)


def sign_document(pdf_bytes, *, nama, jabatan, institusi, private_key, db_path,
                  base_url="http://localhost:8501", tanggal=None):
    """Tanda tangani PDF. Kembalikan (pdf_bertanda_tangan, doc_id)."""
    tanggal = tanggal or date.today().isoformat()
    doc_id = secrets.token_hex(8)  # 16 karakter hex, acak (CSPRNG)

    payload = qr.build_payload(doc_id, nama, jabatan, tanggal, institusi, base_url)
    qr_img = qr.make_qr_image(qr.payload_to_text(payload))
    caption = [
        "Ditandatangani secara digital",
        f"{nama} - {jabatan}",
        f"{institusi}, {tanggal}",
        f"ID: {doc_id}",
    ]
    stamped = stamp_qr(pdf_bytes, qr_img, caption)

    # Hash dihitung dari PDF SETELAH QR ditempel (desain Opsi 1).
    digest = hash_bytes(stamped)
    signature = sign_digest(private_key, digest)

    storage.save_document(
        db_path, doc_id=doc_id, nama=nama, jabatan=jabatan,
        institusi=institusi, tanggal=tanggal, doc_hash=digest,
        signature=signature,
    )
    return stamped, doc_id


def verify_document(pdf_bytes, *, public_key, db_path, doc_id=None) -> VerifyResult:
    """Verifikasi PDF. doc_id opsional (mis. dari URL hasil scan QR); bila
    kosong, QR dibaca dari PDF."""
    payload = None
    if doc_id is None:
        payload = qr.decode_qr_from_pdf(pdf_bytes)
        if payload is None:
            return VerifyResult(False, "QR_TIDAK_TERBACA",
                                "QR-Code tidak ditemukan atau tidak terbaca.")
        doc_id = payload["doc_id"]

    record = storage.get_document(db_path, doc_id)
    if record is None:
        return VerifyResult(False, "DOC_ID_TIDAK_DIKENAL",
                            "Dokumen tidak terdaftar (QR palsu atau tidak dikenal).")

    digest = hash_bytes(pdf_bytes)
    if not verify_digest(public_key, digest, record["signature"]):
        if digest != record["doc_hash"]:
            return VerifyResult(False, "DOKUMEN_DIUBAH",
                                "Isi dokumen berbeda dari saat ditandatangani.")
        return VerifyResult(False, "KUNCI_TIDAK_COCOK",
                            "Tanda tangan tidak cocok dengan kunci publik ini.")

    if payload is not None:
        for name in FIELDS_DICEK:
            if payload.get(name) != record[name]:
                return VerifyResult(False, "METADATA_TIDAK_COCOK",
                                    f"Metadata QR tidak sesuai catatan ({name}).")

    metadata = {name: record[name] for name in FIELDS_DICEK}
    metadata["doc_id"] = doc_id
    return VerifyResult(True, "VALID", "Dokumen asli dan tidak diubah.", metadata)
