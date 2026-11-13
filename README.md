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

Data contoh semuanya dummy ("(sample)"). Untuk mengisi ulang: hapus `instance/crm.db`, jalankan `seed` lagi.

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

## Paket awal dari Mas Gilang

Isi asli README paket awal (13 Nov 2026), disimpan apa adanya:


Starter project for continuing the CRM build in Claude Code.

### Contents
| Path | What |
|---|---|
| `CLAUDE.md` | Project memory: context, agreed decisions, working rules, roadmap. Claude Code reads it automatically. |
| `KICKOFF_PROMPT.md` | The first message to paste into Claude Code |
| `model/index.html` | Working model: all screens and rules, plain JavaScript |
| `model/seed.json` | Dummy data (22 enquiries, 18 requests, 9 catalog items) |
| `tools/gen_seed.py` | Regenerates the dummy data |
| `docs/IT_Handover.md` | Data model, rules, role matrix, gaps versus production |
| `docs/Tradecorp_CRM_Mockup_v0.3.pdf` | Static mock-up and architecture diagram |
| `docs/LINKS.md` | Links to the live model, PRD and guides |

### How to start
1. Unzip to a folder you keep projects in.
2. Open that folder in Claude Code.
3. Paste the text from `KICKOFF_PROMPT.md`.

### Status
- Works today: the model as a Claude artifact (shared database).
- Not yet: running standalone on a PC with saved data (first Claude Code task).
- Blocked on IT: Entra app registration for real login and SharePoint data.

### Tools used
Claude (chat) for the PRD, model and guides; Playwright for the click-through test; Python for seed data.

### 4D self-check
- Delegation: Claude packaged the project and wrote CLAUDE.md from the agreed decisions. G chooses where it lives and what Claude Code builds first.
- Description: decisions copied from the PRD (sections 9a to 9l) as of 12 Nov 2026.
- Discernment: only dummy data is included. Real staff first names and codes are in the model. The PRD text itself is not in the pack, only linked.
- Diligence: verify CLAUDE.md matches your understanding before the first Claude Code session; it will be treated as the source of truth.
