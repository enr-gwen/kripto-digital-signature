# Aplikasi Digital Signature (ECDSA P-256 + QR-Code)

Tugas Proyek Aplikasi Kriptografi, Keamanan Informasi, Informatika UNSIL.
Topik D: Digital Signature.

**Penyusun:** Bunga Rylla Octaramadhany 247006111068

## Deskripsi
Aplikasi untuk menandatangani dokumen PDF secara digital dan memverifikasi
keaslian dokumen serta identitas penandatangan lewat QR-Code.

## Algoritma
- Hash: SHA-256
- Tanda tangan: ECDSA P-256 (pembanding opsional: RSA-2048 PSS)
- Private key disimpan terenkripsi (passphrase dari `.env`), tidak ada di kode sumber

## Desain Alur

### 1. Penandatanganan
```mermaid
flowchart TD
    A[Upload PDF + isi metadata] --> B[Buat doc_id acak]
    B --> C[Buat QR: doc_id + metadata + link verifikasi]
    C --> D[Stempel QR ke PDF]
    D --> E[SHA-256 dari PDF ber-QR]
    E --> F[Sign hash + metadata dengan private key ECDSA]
    F --> G[(Simpan doc_id, metadata, signature, hash)]
    F --> H[Unduh PDF bertanda tangan]
```

### 2. Verifikasi
```mermaid
flowchart TD
    A[Upload PDF + scan/baca QR] --> B{doc_id ada di database?}
    B -- Tidak --> X[GAGAL: QR palsu / tidak dikenal]
    B -- Ya --> C{Metadata QR = metadata tersimpan?}
    C -- Tidak --> X2[GAGAL: metadata dipalsukan]
    C -- Ya --> D[SHA-256 dari PDF yang diunggah]
    D --> E{Verifikasi signature dengan public key}
    E -- Valid --> OK[VALID: dokumen asli]
    E -- Gagal --> X3[GAGAL: dokumen diubah / kunci tidak cocok]
```

## Desain QR
- Isi QR: `doc_id`, nama, jabatan, tanggal, institusi, URL verifikasi
- Signature disimpan di database (dicari lewat `doc_id`), bukan di dalam QR,
  karena QR ditempel sebelum hash dihitung
- Yang di-hash dan ditandatangani adalah PDF **setelah** QR ditempel,
  sehingga mengubah 1 byte apa pun membuat verifikasi gagal

## Instalasi
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # lalu isi KEY_PASSPHRASE
```

## Menjalankan

1. Buat pasangan kunci pertama kali (cukup sekali, sebelum menjalankan aplikasi):
```bash
   python3 -c "from app import keys; keys.save_keypair('keys', 'penandatangan', keys.get_passphrase())"
```
2. Jalankan aplikasi web:
```bash
   streamlit run app/ui.py
```
3. Buka `http://localhost:8501` di browser (biasanya terbuka otomatis).
4. Gunakan tab **Tanda Tangan** untuk menandatangani PDF, dan tab **Verifikasi** untuk memeriksa keasliannya.
## Pengujian
```bash
pytest
```

## Struktur Folder
```
.
├── app/            # kode aplikasi (crypto, qr, pdf, ui)
├── tests/          # unit test
├── data_uji/       # berkas uji (PDF, hasil tamper)
├── hasil_uji/      # tabel/grafik XLSX
├── README.md
├── requirements.txt
└── .env.example
```

## Penggunaan AI
Bagian yang dibantu AI dicatat di lampiran laporan.
