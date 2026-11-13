"""Aturan bisnis CRM (acuan: model HTML Mas Gilang, IT_Handover.md bagian 3).

Fungsi di sini murni (tanpa database, tanpa Flask) supaya gampang dites.
Semua waktu yang masuk adalah UTC naive; jam kerja dihitung di zona waktu region.
"""

import re
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------- organisasi
REGIONS = {
    "SBY": ("Surabaya, Bali, NTB, Papua", "Asia/Jakarta"),
    "BPN": ("Balikpapan", "Asia/Makassar"),   # WITA
    "JKT": ("Jakarta", "Asia/Jakarta"),
}
DEFAULT_TZ = "Asia/Jakarta"

DEPTS = {  # target hari kerja, kapasitas slot per hari
    "Drafter": (3, 10),
    "Estimator": (2, 8),
    "Purchasing": (3, None),
    "Trucking": (2, None),
    "Depo": (1, None),
    "Branch": (2, None),
    "Sales Support": (2, None),
}
DEPT_NAMES = list(DEPTS)

ROLES = {
    "sales": "Sales",
    "rm": "Regional Manager",
    "mgmt": "Management",
    "support": "Tim support",
    "admin": "Administrator",
}

# ---------------------------------------------------------------- pilihan
SOURCES = ["Central", "Direct email", "WhatsApp"]
LINES = ["Container", "Modular", "Modification"]
TYPES = ["Retail", "Project"]
STATUS = ["New", "Contacted", "Ongoing", "No response", "Won", "Lost", "Not prospectable"]
OPEN = ["New", "Contacted", "Ongoing", "No response"]
LOSS = ["Price", "Lead time", "Specification", "Competitor", "Budget cancelled", "No response"]
NOT_PROSPECT = ["Bukan target pasar", "Data palsu / spam", "Hanya tanya-tanya", "Lokasi tidak terjangkau", "Lainnya"]
WON_STAGES = ["PO received", "WO approval", "WO / Kickoff", "Production", "Delivered", "BAST signed", "Handed to Finance"]
REJECT_REASONS = ["Permintaan tidak jelas", "Informasi kurang", "Timeline tidak realistis", "Di luar cakupan"]

KYC = [
    ("identity", "Identitas terverifikasi (orang + perusahaan)", 20),
    ("repeat", "Pelanggan lama", 15),
    ("need", "Kebutuhan jelas, tahu apa yang dibeli", 15),
    ("layout", "Ada layout atau gambar", 15),
    ("qty", "Jumlah diketahui", 10),
    ("timeline", "Timeline diketahui", 10),
    ("location", "Lokasi diketahui", 5),
    ("budget", "Budget atau pengambil keputusan diketahui", 10),
]
KYC_KEYS = [k for k, _, _ in KYC]

PO_CHECK = [
    ("drawing", "Gambar disetujui pelanggan (tanda tangan, email, atau lisan: siapa dan kapan)"),
    ("quote", "Penawaran final dengan nomor revisi"),
    ("match", "PO cocok dengan penawaran: item, jumlah, harga"),
    ("terms", "Syarat PO jelas: denda telat, garansi, pengiriman"),
    ("timeline", "Timeline produksi dan tanggal kirim"),
    ("payment", "Syarat bayar: DP, progres, saat BAST"),
]

# ---------------------------------------------------------------- SLA (jam kerja)
SLA = {
    "contact": 4,     # kontak pertama
    "reassign": 8,    # RM boleh alihkan
    "update": 27,     # update status tiap 3 hari kerja
    "follow": 9,      # follow-up harian setelah penawaran
    "lost": 7,        # hari kalender tanpa respons
    "nofb": 4,        # request tanpa tanggapan
    "rmflag": 9,      # request tanpa tanggapan 1 hari -> RM
    "dup": 60,        # jendela cek duplikat (hari)
}
DAY_START, DAY_END = 8, 17
DAY_HOURS = DAY_END - DAY_START


def tz_of(region):
    return REGIONS.get(region or "", (None, DEFAULT_TZ))[1]


def to_local(dt, tzname=DEFAULT_TZ):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tzname))


def biz_hours(a, b, tzname=DEFAULT_TZ, holidays=frozenset()):
    """Jam kerja (Sen-Jum 08-17 waktu lokal, tanpa hari libur) antara dua waktu UTC."""
    if not a or not b or b <= a:
        return 0.0
    tz = ZoneInfo(tzname)
    la, lb = to_local(a, tzname), to_local(b, tzname)
    total, d = 0.0, la.date()
    while d <= lb.date():
        if d.weekday() < 5 and d not in holidays:
            s = datetime(d.year, d.month, d.day, DAY_START, tzinfo=tz)
            e = datetime(d.year, d.month, d.day, DAY_END, tzinfo=tz)
            s2, e2 = max(s, la), min(e, lb)
            if e2 > s2:
                total += (e2 - s2).total_seconds() / 3600
        d += timedelta(days=1)
    return total


def add_biz_days(t, n, tzname=DEFAULT_TZ, holidays=frozenset()):
    """Tambah n hari kerja ke waktu UTC t (jam tetap sama)."""
    d = t
    while n > 0:
        d += timedelta(days=1)
        ld = to_local(d, tzname).date()
        if ld.weekday() < 5 and ld not in holidays:
            n -= 1
    return d


def add_biz_hours(t, hours, tzname=DEFAULT_TZ, holidays=frozenset()):
    """Waktu UTC setelah `hours` jam kerja dihitung dari t."""
    tz = ZoneInfo(tzname)
    cur = to_local(t, tzname)
    left = hours
    for _ in range(400):
        d = cur.date()
        if d.weekday() < 5 and d not in holidays:
            s = datetime(d.year, d.month, d.day, DAY_START, tzinfo=tz)
            e = datetime(d.year, d.month, d.day, DAY_END, tzinfo=tz)
            start = max(cur, s)
            if start < e:
                avail = (e - start).total_seconds() / 3600
                if avail >= left:
                    return (start + timedelta(hours=left)).astimezone(timezone.utc).replace(tzinfo=None)
                left -= avail
        nd = d + timedelta(days=1)
        cur = datetime(nd.year, nd.month, nd.day, DAY_START, tzinfo=tz)
    return t


def fmt_hours(h):
    if h is None:
        return "–"
    if h < 1:
        return f"{max(1, round(h * 60))} mnt"
    if h < DAY_HOURS:
        return f"{h:.1f} jam"
    return f"{h / DAY_HOURS:.1f} hari"


# ---------------------------------------------------------------- KYC & tier
def kyc_score(kyc, red_flags=0):
    kyc = kyc or {}
    s = sum(p for k, _, p in KYC if kyc.get(k))
    return max(0, min(100, s - 10 * (red_flags or 0)))


def tier(score, price_check=False):
    if price_check:
        return "P"
    return "A" if score >= 70 else "B" if score >= 40 else "C"


TIER_ORDER = {"A": 0, "B": 1, "C": 2, "P": 3}


# ---------------------------------------------------------------- duplikat
_LEGAL = {"pt", "cv", "tbk", "ud", "persero", "pd", "fa", "koperasi", "yayasan"}


def company_key(name):
    words = re.sub(r"\(.*?\)", " ", (name or "").lower())
    words = re.sub(r"[^a-z0-9 ]", " ", words).split()
    return " ".join(w for w in words if w not in _LEGAL)


def phone_key(phone):
    d = re.sub(r"\D", "", phone or "")
    if d.startswith("62"):
        d = "0" + d[2:]
    return d if len(d) > 6 else ""


def email_key(email):
    return (email or "").strip().lower()


# ---------------------------------------------------------------- SLA status
def enquiry_sla(status, stage, received, last_update, now, tzname, holidays):
    """Kembalikan dict(k=kode, t=teks, bad=bool, h=jam)."""
    if status == "New":
        h = biz_hours(received, now, tzname, holidays)
        if h > SLA["reassign"]:
            return dict(k="reassign", t=f"Belum dihubungi {fmt_hours(h)}", bad=True, h=h)
        if h > SLA["contact"]:
            return dict(k="breach", t=f"Belum dihubungi {fmt_hours(h)}", bad=True, h=h)
        return dict(k="ok", t=f"Hubungi dalam {fmt_hours(SLA['contact'] - h)}", bad=False, h=h)
    if status == "No response":
        days = (now - last_update).total_seconds() / 86400
        if days >= SLA["lost"]:
            return dict(k="autolost", t=f"Diam {int(days)} hari", bad=True, h=days)
        return dict(k="ok", t=f"Otomatis lost dalam {int(SLA['lost'] - days + 0.999)} hari", bad=False, h=days)
    if status in OPEN:
        h = biz_hours(last_update, now, tzname, holidays)
        if stage == "Quote sent":
            if h > SLA["follow"]:
                return dict(k="followup", t="Follow-up harian belum dicatat", bad=True, h=h)
            return dict(k="ok", t="Follow-up tercatat", bad=False, h=h)
        if h > SLA["update"]:
            return dict(k="overdue", t=f"Update status telat {fmt_hours(h - SLA['update'])}", bad=True, h=h)
        return dict(k="ok", t=f"Update dalam {fmt_hours(SLA['update'] - h)}", bad=False, h=h)
    return dict(k="closed", t="", bad=False, h=0)


def request_state(status, sent_at, due, now, tzname, holidays):
    """bucket: open / late / done; nofb + rm untuk request tanpa tanggapan."""
    if status == "pending":
        return dict(b="open", t="Urgent: menunggu RM", cls="warn", nofb=False, rm=False, h=0)
    if status == "sent":
        h = biz_hours(sent_at, now, tzname, holidays)
        if h > SLA["nofb"]:
            return dict(b="open", t=f"Belum ditanggapi {fmt_hours(h)}", cls="bad", nofb=True, rm=h > SLA["rmflag"], h=h)
        return dict(b="open", t="Menunggu diterima", cls="warn", nofb=False, rm=False, h=h)
    if status == "accepted":
        if due and now > due:
            return dict(b="late", t="Telat dari target", cls="bad", nofb=False, rm=False, h=0)
        return dict(b="open", t="Dikerjakan", cls="ok", nofb=False, rm=False, h=0)
    label = {"returned": "Sudah dikembalikan", "rejected": "Ditolak", "redirected": "Dialihkan ke katalog"}.get(status, status)
    return dict(b="done", t=label, cls="mute", nofb=False, rm=False, h=0)
