"""Alur utama: sign_document() dan verify_document().

Mendukung tanda tangan tunggal maupun MULTI-SIGNER SEKUENSIAL: beri
`parent_doc_id` (doc_id hasil tanda tangan sebelumnya) untuk menambahkan
tanda tangan susulan pada dokumen yang sama (mis. Ketua lalu Dekan).

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
    riwayat: list = field(default_factory=list)  # daftar tanda tangan (multi-signer)


def sign_document(pdf_bytes, *, nama, jabatan, institusi, private_key, db_path,
                  base_url="http://localhost:8501", tanggal=None,
                  parent_doc_id=None):
    """Tandatangani PDF. Kembalikan (pdf_bertanda_tangan, doc_id).

    Bila `parent_doc_id` diisi, `pdf_bytes` HARUS berisi PDF hasil tanda
    tangan sebelumnya (yang doc_id-nya = parent_doc_id): stempel QR baru
    ditumpuk di atas stempel yang sudah ada, membentuk rantai tanda tangan.
    """
    tanggal = tanggal or date.today().isoformat()
    doc_id = secrets.token_hex(8)  # 16 karakter hex, acak (CSPRNG)

    urutan = 1
    if parent_doc_id is not None:
        induk = storage.get_document(db_path, parent_doc_id)
        if induk is None:
            raise ValueError(
                f"parent_doc_id '{parent_doc_id}' tidak ditemukan di database.")
        urutan = induk["urutan"] + 1

    payload = qr.build_payload(doc_id, nama, jabatan, tanggal, institusi,
                               base_url, urutan=urutan)
    qr_img = qr.make_qr_image(qr.payload_to_text(payload))
    caption = [
        f"Tanda tangan ke-{urutan}",
        f"{nama} - {jabatan}",
        f"{institusi}, {tanggal}",
        f"ID: {doc_id}",
    ]
    stamped = stamp_qr(pdf_bytes, qr_img, caption, slot=urutan - 1)

    # Hash dihitung dari PDF SETELAH QR ditempel (mencakup SEMUA stempel
    # sebelumnya bila ini bagian dari rantai multi-signer).
    digest = hash_bytes(stamped)
    signature = sign_digest(private_key, digest)

    storage.save_document(
        db_path, doc_id=doc_id, nama=nama, jabatan=jabatan,
        institusi=institusi, tanggal=tanggal, doc_hash=digest,
        signature=signature, parent_doc_id=parent_doc_id, urutan=urutan,
    )
    return stamped, doc_id


def verify_document(pdf_bytes, *, public_key, db_path, doc_id=None) -> VerifyResult:
    """Verifikasi PDF terhadap TANDA TANGAN TERAKHIR (paling final) dalam
    dokumen. Mendukung dokumen bertanda tangan tunggal maupun multi-signer.

    `doc_id` opsional: bila kosong, semua QR di halaman terakhir dibaca, dan
    kandidat yang hash-nya cocok dengan dokumen saat ini dipakai (itulah
    tanda tangan paling akhir, karena hanya tanda tangan itu yang mencakup
    seluruh isi dokumen termasuk stempel-stempel sebelumnya).
    """
    digest = hash_bytes(pdf_bytes)

    if doc_id is not None:
        kandidat_ids = [doc_id]
    else:
        payloads = qr.decode_all_qr_from_pdf(pdf_bytes)
        if not payloads:
            return VerifyResult(False, "QR_TIDAK_TERBACA",
                                "QR-Code tidak ditemukan atau tidak terbaca.")
        # Urutan terbesar dulu: tanda tangan paling akhir yang paling mungkin cocok.
        kandidat_ids = [p["doc_id"] for p in
                       sorted(payloads, key=lambda p: p.get("urutan", 1),
                              reverse=True)]

    record = None
    for cid in kandidat_ids:
        rec = storage.get_document(db_path, cid)
        if rec is not None and rec["doc_hash"] == digest:
            record = rec
            break

    if record is None:
        # Tidak ada kandidat yang cocok: cek dulu apakah semuanya tak dikenal,
        # atau ada yang dikenal tapi isinya sudah berubah (tamper).
        dikenal = [storage.get_document(db_path, cid) for cid in kandidat_ids]
        dikenal = [d for d in dikenal if d is not None]
        if not dikenal:
            return VerifyResult(False, "DOC_ID_TIDAK_DIKENAL",
                                "Dokumen tidak terdaftar (QR palsu atau tidak dikenal).")
        record = dikenal[-1]  # dipakai untuk pesan/derajat kecocokan berikutnya

    if not verify_digest(public_key, digest, record["signature"]):
        if digest != record["doc_hash"]:
            return VerifyResult(False, "DOKUMEN_DIUBAH",
                                "Isi dokumen berbeda dari saat ditandatangani.")
        return VerifyResult(False, "KUNCI_TIDAK_COCOK",
                            "Tanda tangan tidak cocok dengan kunci publik ini.")

    riwayat = storage.get_chain(db_path, record["doc_id"])
    if doc_id is None:
        # Cocokkan tiap payload QR dengan metadata tersimpan (deteksi metadata dipalsukan).
        by_id = {p["doc_id"]: p for p in payloads}
        for entry in riwayat:
            p = by_id.get(entry["doc_id"])
            if p is None:
                continue
            for name in FIELDS_DICEK:
                if p.get(name) != entry[name]:
                    return VerifyResult(False, "METADATA_TIDAK_COCOK",
                                        f"Metadata QR tidak sesuai catatan ({name}).")

    metadata = {name: record[name] for name in FIELDS_DICEK}
    metadata["doc_id"] = record["doc_id"]
    metadata["urutan"] = record["urutan"]
    pesan = ("Dokumen asli dan tidak diubah."
            if len(riwayat) == 1 else
            f"Dokumen asli, ditandatangani {len(riwayat)} pihak secara berurutan.")
    return VerifyResult(True, "VALID", pesan, metadata, riwayat)
