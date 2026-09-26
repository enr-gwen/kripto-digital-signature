"""Antarmuka Streamlit: halaman Tanda Tangan dan Verifikasi.

Jalankan dari folder utama proyek:
    streamlit run app/ui.py
UI hanya memanggil service.sign_document() dan service.verify_document().
"""
import os
import sys
from datetime import date
from pathlib import Path

# Agar `from app import ...` bekerja saat dijalankan lewat `streamlit run`.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app import keys, qr, service  # noqa: E402

PRIVATE_KEY_PATH = ROOT / "keys" / "penandatangan.key"
PUBLIC_KEY_PATH = ROOT / "keys" / "penandatangan.pub"
DB_PATH = ROOT / "storage" / "documents.db"
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8501")
MAX_BYTES = 20 * 1024 * 1024  # batas 20 MB

DB_PATH.parent.mkdir(exist_ok=True)

st.set_page_config(page_title="Digital Signature")
st.title(" Digital Signature")
st.caption("ECDSA P-256 + SHA-256 · QR-Code untuk verifikasi")

if not PRIVATE_KEY_PATH.exists() or not PUBLIC_KEY_PATH.exists():
    st.error(
        "Key pair belum ada di folder `keys/`. Buat dulu dengan perintah:\n\n"
        "`python3 -c \"from app import keys; keys.save_keypair('keys', "
        "'penandatangan', keys.get_passphrase())\"`"
    )
    st.stop()


def read_pdf(uploaded):
    """Kembalikan bytes PDF, atau None (dan tampilkan error) bila tidak sah."""
    data = uploaded.getvalue()
    if len(data) > MAX_BYTES:
        st.error("Berkas terlalu besar (maksimal 20 MB).")
        return None
    if not data.startswith(b"%PDF"):
        st.error("Berkas bukan PDF yang valid.")
        return None
    return data


tab_sign, tab_verify = st.tabs(["✍️ Tanda Tangan", "🔍 Verifikasi"])

# ---------------------------------------------------------------- TANDA TANGAN
with tab_sign:
    st.subheader("Tandatangani dokumen PDF")
    pdf_file = st.file_uploader("Unggah PDF", type=["pdf"], key="sign_pdf")
    nama = st.text_input("Nama penandatangan")
    jabatan = st.text_input("Jabatan")
    institusi = st.text_input("Institusi", value="Universitas Siliwangi")
    st.text_input("Tanggal", value=date.today().isoformat(), disabled=True)

    if st.button("Tandatangani", type="primary"):
        if pdf_file is None or not (nama.strip() and jabatan.strip()
                                    and institusi.strip()):
            st.warning("Lengkapi PDF, nama, jabatan, dan institusi.")
        else:
            pdf_bytes = read_pdf(pdf_file)
            if pdf_bytes is not None:
                try:
                    private_key = keys.load_private_key(
                        PRIVATE_KEY_PATH.read_bytes(), keys.get_passphrase())
                    signed, doc_id = service.sign_document(
                        pdf_bytes, nama=nama.strip(), jabatan=jabatan.strip(),
                        institusi=institusi.strip(), private_key=private_key,
                        db_path=DB_PATH, base_url=BASE_URL)
                except RuntimeError as e:
                    st.error(str(e))
                except ValueError:
                    st.error("Passphrase di `.env` tidak cocok dengan private key.")
                except Exception as e:  # PDF rusak, dll.
                    st.error(f"Gagal menandatangani: {e}")
                else:
                    st.session_state["signed"] = {
                        "pdf": signed, "doc_id": doc_id,
                        "filename": Path(pdf_file.name).stem + "_signed.pdf",
                    }

    signed = st.session_state.get("signed")
    if signed:
        st.success(f"Dokumen berhasil ditandatangani. ID: `{signed['doc_id']}`")
        st.download_button("⬇️ Unduh PDF bertanda tangan", data=signed["pdf"],
                           file_name=signed["filename"],
                           mime="application/pdf")
        st.info("Jangan buka lalu simpan ulang PDF ini di aplikasi lain. "
                "Perubahan byte sekecil apa pun membuat verifikasi gagal.")

# ------------------------------------------------------------------ VERIFIKASI
with tab_verify:
    st.subheader("Verifikasi dokumen")

    url_doc_id = st.query_params.get("doc_id")
    if url_doc_id and not qr.DOC_ID_RE.match(url_doc_id):
        st.warning("Parameter `doc_id` pada URL tidak valid; diabaikan.")
        url_doc_id = None
    if url_doc_id:
        st.info(f"Diverifikasi terhadap ID dari tautan QR: `{url_doc_id}`")

    verify_file = st.file_uploader("Unggah PDF bertanda tangan", type=["pdf"],
                                   key="verify_pdf")
    sumber = st.radio(
        "Kunci publik",
        ["Kunci publik aplikasi", "Unggah kunci publik lain (uji kunci salah)"],
    )
    other_pub = None
    if sumber != "Kunci publik aplikasi":
        other_pub = st.file_uploader("Berkas kunci publik (.pub / .pem)",
                                     type=["pub", "pem"], key="verify_pub")

    if st.button("Verifikasi", type="primary"):
        if verify_file is None:
            st.warning("Unggah PDF terlebih dahulu.")
        elif sumber != "Kunci publik aplikasi" and other_pub is None:
            st.warning("Unggah berkas kunci publik.")
        else:
            pdf_bytes = read_pdf(verify_file)
            if pdf_bytes is not None:
                try:
                    pem = (PUBLIC_KEY_PATH.read_bytes() if other_pub is None
                           else other_pub.getvalue())
                    public_key = keys.load_public_key(pem)
                except Exception:
                    st.error("Berkas kunci publik tidak valid.")
                else:
                    hasil = service.verify_document(
                        pdf_bytes, public_key=public_key, db_path=DB_PATH,
                        doc_id=url_doc_id)
                    if hasil.valid:
                        st.success(f"✅ VALID: {hasil.message}")
                        st.table({"Data": ["ID", "Nama", "Jabatan", "Institusi",
                                           "Tanggal"],
                                  "Isi": [hasil.metadata["doc_id"],
                                          hasil.metadata["nama"],
                                          hasil.metadata["jabatan"],
                                          hasil.metadata["institusi"],
                                          hasil.metadata["tanggal"]]})
                    else:
                        st.error(f"❌ TIDAK VALID ({hasil.status}): {hasil.message}")
