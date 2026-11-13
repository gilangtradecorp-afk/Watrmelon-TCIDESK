"""Logika yang butuh database: jam sekarang, hak akses, log, nomor ENQ, chat & notifikasi."""

import re
from datetime import datetime, timezone

from flask import current_app, g, has_app_context, url_for
from sqlalchemy import or_, update

from . import db
from .models import (Activity, Channel, Counter, Customer, Enquiry, Holiday, Message, Notification,
                     Request, User)
from .rules import (KYC_KEYS, SLA, company_key, email_key, enquiry_sla, kyc_score, phone_key,
                    request_state, tier, to_local, tz_of)


# ---------------------------------------------------------------- waktu
def now():
    demo = current_app.config.get("DEMO_NOW") if has_app_context() else ""
    if demo:
        return datetime.fromisoformat(demo).astimezone(timezone.utc).replace(tzinfo=None)
    return datetime.now(timezone.utc).replace(tzinfo=None)


def holidays():
    if "holidays" not in g:
        g.holidays = frozenset(h.day for h in Holiday.query.all())
    return g.holidays


def sla(e):
    return enquiry_sla(e.status, e.stage, e.received, e.last_update, now(), e.tz, holidays())


def rstate(r):
    return request_state(r.status, r.sent_at, r.due, now(), tz_of(r.region), holidays())


def next_action(e):
    """(teks aksi berikutnya, jatuh tempo UTC) untuk daftar tugas sales."""
    from .rules import add_biz_hours, DEPTS
    tz, hol = e.tz, holidays()
    if e.status == "New":
        return "Kontak pertama", add_biz_hours(e.received, SLA["contact"], tz, hol)
    if e.status == "No response":
        from datetime import timedelta
        return "Hubungi lagi atau tutup", e.last_update + timedelta(days=SLA["lost"])
    if e.status == "Won":
        return {"PO received": "Lengkapi checklist PO", "WO approval": "Tunggu persetujuan RM"}.get(e.stage, f"Kawal tahap {e.stage}"), None
    if not e.is_open:
        return "", None
    if e.stage == "Quote sent":
        return "Follow-up harian + bukti", add_biz_hours(e.last_update, SLA["follow"], tz, hol)
    waiting = [r for r in e.requests if r.status in ("sent", "accepted", "pending")]
    if waiting:
        r = waiting[0]
        what = {"Drafter": "gambar", "Estimator": "harga"}.get(r.dept, "jawaban")
        return f"Tunggu {what} dari {r.dept}", r.due or add_biz_hours(r.sent_at, SLA["nofb"], tz, hol)
    missing = [k for k in KYC_KEYS if not (e.kyc or {}).get(k)]
    if missing and e.stage in ("KYC", "New"):
        return f"Lengkapi KYC ({len(KYC_KEYS) - len(missing)}/{len(KYC_KEYS)})", add_biz_hours(e.last_update, SLA["update"], tz, hol)
    return "Update status", add_biz_hours(e.last_update, SLA["update"], tz, hol)


def sla_clock(e):
    """Isi kartu Jam SLA di detail enquiry: list (ok?, teks)."""
    from .rules import add_biz_hours, biz_hours, fmt_hours
    tz, hol, n = e.tz, holidays(), now()
    out = []
    if e.contacted_at:
        h = biz_hours(e.received, e.contacted_at, tz, hol)
        out.append((h <= SLA["contact"], f"Kontak pertama {fmt_hours(h)} (maks. {SLA['contact']} jam)"))
    else:
        h = biz_hours(e.received, n, tz, hol)
        out.append((h <= SLA["contact"], f"Belum dihubungi, sudah {fmt_hours(h)} (maks. {SLA['contact']} jam)"))
    if e.is_open and e.status != "New":
        due = add_biz_hours(e.last_update, SLA["follow"] if e.stage == "Quote sent" else SLA["update"], tz, hol)
        label = "Follow-up berikutnya" if e.stage == "Quote sent" else "Update 3 hari berikutnya"
        out.append((n <= due, f"{label} paling lambat {to_local(due, tz):%d %b %H:%M}"))
    return out


def week_start(t, region):
    from datetime import timedelta
    loc = to_local(t, tz_of(region))
    monday = (loc - timedelta(days=loc.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.astimezone(timezone.utc).replace(tzinfo=None)


def urgent_used(seller_code, region):
    return Request.query.filter(Request.seller_code == seller_code, Request.urgent.is_(True),
                                Request.sent_at >= week_start(now(), region)).count()


def proof_rate(seller_code):
    q = Activity.query.filter(Activity.seller_code == seller_code, Activity.kind.in_(("contact", "followup")))
    total = q.count()
    return (q.filter(Activity.has_proof.is_(True)).count(), total)


# ---------------------------------------------------------------- hak akses
def enquiry_query(u):
    q = Enquiry.query
    if u.role == "sales":
        return q.filter(Enquiry.seller_code == u.code)
    if u.role == "rm":
        return q.filter(Enquiry.region == u.region)
    if u.role == "support":
        ids = db.session.query(Request.enquiry_id).filter(Request.dept == u.team)
        return q.filter(Enquiry.id.in_(ids))
    return q


def request_query(u):
    q = Request.query
    if u.role == "sales":
        return q.filter(Request.seller_code == u.code)
    if u.role == "rm":
        return q.filter(Request.region == u.region)
    if u.role == "support":
        return q.filter(Request.dept == u.team)
    return q


def can_see(u, e):
    if u.role in ("mgmt", "admin"):
        return True
    if u.role == "sales":
        return e.seller_code == u.code
    if u.role == "rm":
        return e.region == u.region
    if u.role == "support":
        return any(r.dept == u.team for r in e.requests)
    return False


def can_edit(u, e):
    return (u.role == "sales" and e.seller_code == u.code) or (u.role == "rm" and e.region == u.region) or u.role == "admin"


def can_act_request(u, r):
    return (u.role == "rm" and r.region == u.region) or (u.role == "support" and u.team == r.dept) or u.role == "admin"


def is_rm_of(u, region):
    return (u.role == "rm" and u.region == region) or u.role == "admin"


def sellers_in_scope(u, region=None):
    q = User.query.filter(User.code.isnot(None), User.active.is_(True), User.role.in_(("sales", "rm")))
    if u.role == "sales":
        q = q.filter(User.id == u.id)
    elif u.role == "rm":
        q = q.filter(User.region == u.region)
    elif region:
        q = q.filter(User.region == region)
    return q.order_by(User.region, User.role.desc(), User.name).all()


# ---------------------------------------------------------------- log & skor
def log(text, who, enquiry=None, request=None, t=None, kind=None, proof=False, file_name=None, file_path=None):
    a = Activity(enquiry_id=enquiry.id if enquiry else None, request_id=request.id if request else None,
                 t=t or now(), who=who, text=text, kind=kind, seller_code=enquiry.seller_code if enquiry else None,
                 has_proof=bool(proof or file_path), file_name=file_name, file_path=file_path)
    db.session.add(a)
    return a


ALLOWED_UPLOADS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".xlsx", ".xls", ".docx", ".doc", ".dwg", ".zip"}


def save_upload(fs):
    """Simpan file upload, kembalikan (nama, path) atau (None, None). ValueError kalau jenisnya tidak boleh."""
    import os
    import uuid
    from werkzeug.utils import secure_filename
    if not fs or not fs.filename:
        return None, None
    ext = os.path.splitext(fs.filename)[1].lower()
    if ext not in ALLOWED_UPLOADS:
        raise ValueError("Jenis file tidak diizinkan.")
    name = secure_filename(fs.filename) or "file" + ext
    path = f"{uuid.uuid4().hex}{ext}"
    fs.save(os.path.join(current_app.config["UPLOAD_DIR"], path))
    return name, path


def touch(e):
    e.last_update = now()


def rescore(e):
    e.score = kyc_score(e.kyc, e.red_flag_count)
    e.tier = tier(e.score, e.price_check)


def mint(region, seller_code, t):
    """Nomor ENQ: ENQ-{region}-{sales}-{YYMMDD}-{####}, urut per region per tahun (aman dari dobel)."""
    local = to_local(t, tz_of(region))
    year = local.year
    if not db.session.get(Counter, (region, year)):
        db.session.add(Counter(region=region, year=year, last=0))
        db.session.flush()
    db.session.execute(update(Counter).where(Counter.region == region, Counter.year == year)
                       .values(last=Counter.last + 1))
    n = db.session.get(Counter, (region, year))
    db.session.refresh(n)
    return f"ENQ-{region}-{seller_code}-{local:%y%m%d}-{n.last:04d}"


def find_customer_matches(company, phone, email):
    ck, pk, ek = company_key(company), phone_key(phone), email_key(email)
    conds = []
    if ek:
        conds.append(Customer.email_key == ek)
    if pk:
        conds.append(Customer.phone_key == pk)
    if ck:
        conds.append(Customer.company_key == ck)
    if not conds:
        return []
    return Customer.query.filter(or_(*conds)).all()


def recent_enquiries_of(customers):
    """Enquiry pelanggan ini yang masih terbuka atau aktif dalam jendela duplikat."""
    ids = [c.id for c in customers]
    if not ids:
        return []
    out = []
    for e in Enquiry.query.filter(Enquiry.customer_id.in_(ids)).all():
        if e.is_open or (now() - e.last_update).days <= SLA["dup"]:
            out.append(e)
    return out


def is_repeat_customer(customer_id):
    return Enquiry.query.filter_by(customer_id=customer_id, status="Won").count() > 0


def new_kyc():
    return {k: False for k in KYC_KEYS}


# ---------------------------------------------------------------- chat & notifikasi
def channel(key, name=None, kind=None, ref=None):
    c = Channel.query.filter_by(key=key).first()
    if not c:
        c = Channel(key=key, name=name or key, kind=kind or key.split(":")[0], ref=ref)
        db.session.add(c)
        db.session.flush()
    return c


def enquiry_channel(e):
    return channel(f"enq:{e.id}", e.enq_no, "enq", str(e.id))


def region_channel(region):
    return channel(f"region:{region}", f"#{region.lower()}", "region", region)


def team_channel(dept):
    return channel(f"team:{dept}", "#" + dept.lower().replace(" ", "-"), "team", dept)


def can_see_channel(u, c):
    if u.role in ("mgmt", "admin"):
        return c.kind != "dm" or str(u.id) in c.key.split(":")[1:]
    if c.kind == "region":
        return u.region == c.ref
    if c.kind == "team":
        return u.role == "rm" or (u.role == "support" and u.team == c.ref)
    if c.kind == "enq":
        e = db.session.get(Enquiry, int(c.ref))
        return bool(e and can_see(u, e))
    if c.kind == "dm":
        return str(u.id) in c.key.split(":")[1:]
    return False


def notify(users, text, link=None):
    seen = set()
    for u in users:
        if u and u.id not in seen and u.active:
            seen.add(u.id)
            db.session.add(Notification(user_id=u.id, t=now(), text=text, link=link))


def post(c, text, user=None, action=None, file_name=None, file_path=None):
    m = Message(channel_id=c.id, user_id=user.id if user else None, t=now(), text=text, action=action,
                file_name=file_name, file_path=file_path)
    db.session.add(m)
    db.session.flush()
    if user:
        _mentions(c, m, user)
    return m


_MENTION = re.compile(r"@([A-Za-z0-9_.-]{2,40})")


def _mentions(c, m, author):
    names = {x.lower() for x in _MENTION.findall(m.text)}
    if not names:
        return
    hits = [u for u in User.query.filter(User.active.is_(True)).all()
            if u.id != author.id and (u.username.lower() in names or (u.code or "").lower() in names)]
    notify([u for u in hits if can_see_channel(u, c)], f"{author.name} menyebut Anda di {c.name}: {m.text[:120]}",
           url_for("chat.room", cid=c.id))


def rms_of(region):
    return User.query.filter_by(role="rm", region=region, active=True).all()


def seller_user(code):
    return User.query.filter_by(code=code).first()


def team_users(dept):
    return User.query.filter_by(role="support", team=dept, active=True).all()
