"""Penyimpanan SQLite: satu baris per stempel tanda tangan.

Mendukung multi-signer sekuensial lewat parent_doc_id + urutan: tanda tangan
ke-2 (mis. Dekan) menunjuk ke tanda tangan ke-1 (mis. Ketua) yang dilakukan
lebih dulu pada dokumen yang sama.

Semua query memakai parameter (?), bukan string-concatenation, supaya aman
dari SQL injection.
"""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id         TEXT PRIMARY KEY,
    nama           TEXT NOT NULL,
    jabatan        TEXT NOT NULL,
    institusi      TEXT NOT NULL,
    tanggal        TEXT NOT NULL,
    doc_hash       TEXT NOT NULL,   -- SHA-256 (hex) dokumen SAAT tahap ini dibuat
    signature      TEXT NOT NULL,   -- tanda tangan ECDSA (hex, DER)
    parent_doc_id  TEXT NULL,       -- tanda tangan sebelumnya dalam rantai (jika ada)
    urutan         INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL
)
"""
# Kolom yang ditambahkan belakangan (agar database lama tetap kompatibel).
KOLOM_TAMBAHAN = {
    "parent_doc_id": "TEXT NULL",
    "urutan": "INTEGER NOT NULL DEFAULT 1",
}


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path) -> None:
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(SCHEMA)
        kolom_ada = {row["name"] for row in conn.execute(
            "PRAGMA table_info(documents)")}
        for nama, tipe in KOLOM_TAMBAHAN.items():
            if nama not in kolom_ada:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {nama} {tipe}")


def save_document(db_path, *, doc_id, nama, jabatan, institusi, tanggal,
                  doc_hash: bytes, signature: bytes,
                  parent_doc_id=None, urutan: int = 1) -> None:
    init_db(db_path)
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO documents (doc_id, nama, jabatan, institusi, tanggal,"
            " doc_hash, signature, parent_doc_id, urutan, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (doc_id, nama, jabatan, institusi, tanggal, doc_hash.hex(),
             signature.hex(), parent_doc_id, urutan,
             datetime.now(timezone.utc).isoformat()),
        )


def get_document(db_path, doc_id: str):
    """Kembalikan dict dokumen (hash & signature sudah berupa bytes) atau None."""
    init_db(db_path)
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["doc_hash"] = bytes.fromhex(data["doc_hash"])
    data["signature"] = bytes.fromhex(data["signature"])
    return data


def get_chain(db_path, doc_id: str):
    """Kembalikan riwayat tanda tangan dari yang PERTAMA sampai doc_id ini,
    dengan menelusuri parent_doc_id mundur. List kosong bila doc_id tak ada."""
    riwayat = []
    current = get_document(db_path, doc_id)
    seen = set()
    while current is not None and current["doc_id"] not in seen:
        seen.add(current["doc_id"])
        riwayat.append(current)
        parent_id = current["parent_doc_id"]
        current = get_document(db_path, parent_id) if parent_id else None
    riwayat.reverse()
    return riwayat
