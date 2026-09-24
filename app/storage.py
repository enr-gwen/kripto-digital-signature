"""Penyimpanan SQLite: satu baris per dokumen yang sudah ditandatangani.

Semua query memakai parameter (?), bukan string-concatenation, supaya aman
dari SQL injection.
"""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id     TEXT PRIMARY KEY,
    nama       TEXT NOT NULL,
    jabatan    TEXT NOT NULL,
    institusi  TEXT NOT NULL,
    tanggal    TEXT NOT NULL,
    doc_hash   TEXT NOT NULL,   -- SHA-256 (hex) dari PDF yang sudah ber-QR
    signature  TEXT NOT NULL,   -- tanda tangan ECDSA (hex, DER)
    created_at TEXT NOT NULL
)
"""


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path) -> None:
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(SCHEMA)


def save_document(db_path, *, doc_id, nama, jabatan, institusi, tanggal,
                  doc_hash: bytes, signature: bytes) -> None:
    init_db(db_path)
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO documents (doc_id, nama, jabatan, institusi, tanggal,"
            " doc_hash, signature, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (doc_id, nama, jabatan, institusi, tanggal, doc_hash.hex(),
             signature.hex(), datetime.now(timezone.utc).isoformat()),
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
