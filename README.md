# Tradecorp CRM

CRM penjualan Tradecorp (SBY, BPN, JKT) dalam Python Flask. Alur dan aturannya mengacu ke model HTML
dari Mas Gilang (hand-over pack 12 Nov 2026), ditambah perbaikan:

- Jam kerja SLA per zona waktu region (BPN = WITA) dan tanpa hari libur.
- Setiap perubahan KYC, tanda merah (wajib alasan), dan checklist PO tercatat di log.
- "Identitas terverifikasi" dicentang manual, tidak otomatis.
- Cek duplikat menormalkan nama perusahaan (tanpa PT/CV/Tbk) dan nomor telepon.
- Data pelanggan terpisah; "pelanggan lama" otomatis dari riwayat Won.
- Nomor ENQ dibuat server dengan counter per region per tahun (tidak bisa dobel).
- Penawaran Sale/Rental dengan PPN, diskon (di atas batas perlu RM), masa berlaku, PDF.
- Daftar harga yang bisa diubah RM, dengan riwayat perubahan.
- RM bisa mengalihkan enquiry kapan saja dengan alasan; nomor dan nilai PO.
- Chat tim internal: channel region, channel tim, thread per enquiry, pesan langsung,
  mention @kode, lampiran, pesan otomatis + tombol setujui dari sistem.
- Pengingat SLA otomatis tiap 5 menit ke chat + notifikasi (tidak dobel).

Dari mockup v0.3 (11 Nov 2026):

- Meja sales: kolom "Aksi berikutnya" dan "Jatuh tempo"; sales tidak bisa mengambil enquiry baru selama ada
  enquiry yang belum dihubungi lewat 4 jam (`CRM_BLOCK_ON_BREACH=0` untuk mematikan).
- Detail enquiry: kartu Jam SLA, daftar revisi, upload bukti kontak/follow-up (screenshot WA/email).
- Kontrol region: % bukti diunggah, update telat, kuota urgent per minggu (`CRM_URGENT_QUOTA`, default 2),
  keputusan duplikat lintas region, tombol ekspor.
- Penawaran: syarat bayar, hari pengiriman, mode per item, tombol "Salin pesan WA", item custom tanpa harga
  otomatis dikirim ke Estimator.
- Halaman Order (PO), ekspor Excel (enquiry, request, penawaran) untuk RM dan manajemen.
- Beban kerja: Hari ini / Bulan ini, filter sales, grafik enquiry per hari. Win rate 90 hari, kontak pertama 30 hari.
- Login memakai akun aplikasi sendiri (bukan akun Microsoft).

## Jalankan di laptop (development)

Cara paling gampang: klik dua kali **`jalankan.bat`**. Pertama kali ia menyiapkan semuanya sendiri
(lingkungan Python, library, `.env` dengan jam demo, data contoh), lalu membuka browser.
Syaratnya hanya Python 3.14 dan Git sudah terpasang.

Cara manual:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env          # isi SECRET_KEY
.venv\Scripts\python -m flask --app run.py seed
.venv\Scripts\python run.py
```

Buka http://127.0.0.1:5100. Akun demo (password `demo123`, dari `seed.py`):

| Peran | Username |
|---|---|
| Sales | `adi`, `and`, `nov`, `rev`, `yul`, `end`, `evi`, `iva`, `yop`, `wel` |
| Regional Manager | `gil` (SBY), `hen` (BPN), `din` (JKT) |
| Tim support | `drafter`, `estimator`, `purchasing`, `trucking`, `depo`, `branch`, `salessupport` |
| Manajemen | `direktur` |
| Admin | `admin` |

Data contoh semuanya dummy ("(sample)"). Untuk mengisi ulang: hapus `instance/crm.db`, lalu klik `jalankan.bat` lagi.

## Produksi (PC Surabaya)

`python serve.py` (waitress, port 8000), dijadikan Windows Service dengan NSSM, akses luar lewat
Tailscale Funnel akun Mas Gilang. Ganti semua password demo, isi `SECRET_KEY` baru di `.env`.

## Tes

```bash
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest -q tests
```

## Belum ada

Push notifikasi ke HP, intake email otomatis (butuh izin admin M365), migrasi database (Alembic),
backup terjadwal.

## Isi lain di repo

- `CLAUDE.md`: memori proyek untuk Claude Code (keputusan, aturan kerja, peta kode).
- `model/`: model HTML asli Mas Gilang dan `seed.json` (sumber `seed_data.json`). Bisa dijalankan sendiri dengan
  `node server.js` (http://localhost:8080); cara pakai dan catatan perubahannya ada di `model/README.md`.
- `docs/`: IT hand-over, mockup v0.3, tautan PRD.
- `tools/gen_seed.py`: pembuat ulang data contoh.
