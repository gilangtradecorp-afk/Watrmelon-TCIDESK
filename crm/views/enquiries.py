from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from .. import db
from ..models import Activity, Customer, Enquiry, Message, Request, User
from ..rules import (DEPT_NAMES, DEPTS, KYC_KEYS, LINES, LOSS, NOT_PROSPECT, OPEN, PO_CHECK, SOURCES, STATUS,
                     TIER_ORDER, TYPES, WON_STAGES, company_key, email_key, phone_key)
from ..services import (can_edit, can_see, enquiry_channel, enquiry_query, find_customer_matches, is_repeat_customer,
                        is_rm_of, log, mint, new_kyc, notify, now, post, recent_enquiries_of, region_channel,
                        rescore, rms_of, save_upload, seller_user, sellers_in_scope, sla, sla_clock, team_channel,
                        team_users, touch, urgent_used)

bp = Blueprint("enquiries", __name__, url_prefix="/enquiry")


def sort_key(e):
    s = sla(e)
    return (0 if s["bad"] else 1, TIER_ORDER.get(e.tier, 9), -e.received.timestamp())


def get_enquiry(eid, edit=False):
    e = db.session.get(Enquiry, eid) or abort(404)
    if not can_see(current_user, e) or (edit and not can_edit(current_user, e)):
        abort(403)
    return e


def back(e, msg=None, cat="ok"):
    if msg:
        flash(msg, cat)
    return redirect(url_for("enquiries.detail", eid=e.id))


# ---------------------------------------------------------------- daftar
@bp.route("/")
@login_required
def index():
    q = enquiry_query(current_user)
    region = request.args.get("region", "")
    if region and current_user.role in ("mgmt", "admin"):
        q = q.filter(Enquiry.region == region)
    st = request.args.get("status", "open")
    if st == "open":
        q = q.filter(Enquiry.status.in_(OPEN))
    elif st != "all":
        q = q.filter(Enquiry.status == st)
    text = request.args.get("q", "").strip().lower()
    rows = q.all()
    if text:
        rows = [e for e in rows if text in " ".join([e.enq_no, e.customer.company, e.customer.contact or "",
                                                     e.product or "", e.location or ""]).lower()]
    rows.sort(key=sort_key)
    return render_template("enquiries/index.html", rows=rows, st=st, text=text, region=region, STATUS=STATUS, sla=sla)


# ---------------------------------------------------------------- buat baru + cek duplikat
@bp.route("/baru", methods=["GET", "POST"])
@login_required
def new():
    if current_user.role not in ("sales", "rm", "admin"):
        abort(403)
    sellers = sellers_in_scope(current_user)
    f = request.form
    if request.method == "POST":
        if not f.get("company", "").strip() or not f.get("product", "").strip():
            flash("Nama perusahaan dan produk wajib diisi.", "bad")
            return render_template("enquiries/new.html", f=f, sellers=sellers, SOURCES=SOURCES, LINES=LINES, TYPES=TYPES)
        seller = User.query.filter_by(code=f.get("seller")).first()
        if not seller or seller not in sellers:
            abort(403)
        blocked = blocking_breaches(seller)
        if blocked and seller.id == current_user.id:
            flash(f"Belum bisa ambil enquiry baru: {blocked[0].enq_no} belum dihubungi lewat 4 jam kerja. "
                  "Hubungi dulu, atau minta RM mencatatkan enquiry ini.", "bad")
            return redirect(url_for("enquiries.detail", eid=blocked[0].id))
        decision = f.get("decision", "")
        if not decision:
            matches = find_customer_matches(f["company"], f.get("phone"), f.get("email"))
            dups = recent_enquiries_of(matches)
            if dups:
                return render_template("enquiries/duplicate.html", f=f, dups=dups, matches=matches)
        customer = None
        if decision == "linked" and f.get("customer_id"):
            customer = db.session.get(Customer, int(f["customer_id"]))
        e = create_enquiry(f, seller, customer, linked_to=int(f["linked_to"]) if f.get("linked_to") else None)
        other = db.session.get(Enquiry, e.linked_to) if e.linked_to else None
        if other and other.region != e.region and other.is_open:
            e.dup_review = other.id
            log(f"Pelanggan ini juga dipegang {other.seller_code} ({other.region}) di {other.enq_no}. Menunggu keputusan RM.",
                current_user.name, e)
            post(region_channel(e.region), f"🔀 Duplikat lintas region: {e.enq_no} ({e.customer.company}) juga dipegang "
                 f"{other.seller_code} di {other.region} ({other.enq_no}). Perlu keputusan RM.",
                 action={"label": "Buka kontrol region", "url": url_for("dash.region")})
            notify(rms_of(e.region), f"Duplikat lintas region {e.enq_no}: putuskan lanjut atau serahkan ke {other.region}.",
                   url_for("dash.region"))
        db.session.commit()
        return back(e, f"Enquiry {e.enq_no} dibuat.")
    default_src = "WhatsApp" if current_user.role == "sales" else "Central"
    blocked = blocking_breaches(current_user) if current_user.role == "sales" else []
    return render_template("enquiries/new.html", f={"source": default_src, "seller": current_user.code},
                           sellers=sellers, SOURCES=SOURCES, LINES=LINES, TYPES=TYPES, blocked=blocked)


def blocking_breaches(seller):
    """Enquiry milik sales ini yang belum dihubungi lewat batas 4 jam (aturan blokir di mockup)."""
    if not current_app.config["BLOCK_ON_BREACH"] or seller.role != "sales":
        return []
    rows = Enquiry.query.filter_by(seller_code=seller.code, status="New").all()
    return [e for e in rows if sla(e)["k"] in ("breach", "reassign")]


@bp.route("/<int:eid>/duplikat", methods=["POST"])
@login_required
def dup_decide(eid):
    e = get_enquiry(eid)
    if not is_rm_of(current_user, e.region) or not e.dup_review:
        abort(403)
    other = db.session.get(Enquiry, e.dup_review)
    if request.form.get("choice") == "handover" and other:
        e.status, e.close_reason = "Not prospectable", "Lainnya"
        log(f"Duplikat lintas region: diserahkan ke {other.region} ({other.enq_no}, {other.seller_code}).", current_user.name, e)
        log(f"Permintaan baru dari pelanggan yang sama masuk lewat {e.region} ({e.enq_no}: {e.product}). "
            f"Diserahkan ke enquiry ini oleh RM {current_user.name}.", current_user.name, other)
        notify([seller_user(other.seller_code)] + rms_of(other.region),
               f"{e.region} menyerahkan kebutuhan baru {e.customer.company} ke {other.enq_no}.",
               url_for("enquiries.detail", eid=other.id))
        msg = f"Diserahkan ke {other.region}."
    else:
        log(f"Duplikat lintas region: RM memutuskan {e.region} tetap menangani.", current_user.name, e)
        msg = "Tetap ditangani region ini."
    e.dup_review = None
    touch(e)
    db.session.commit()
    flash(msg, "ok")
    return redirect(request.form.get("next") or url_for("dash.region"))


@bp.route("/aktivitas/<int:aid>/file")
@login_required
def activity_file(aid):
    a = db.session.get(Activity, aid) or abort(404)
    if not a.file_path or not a.enquiry_id:
        abort(404)
    get_enquiry(a.enquiry_id)
    import os
    return send_file(os.path.join(current_app.config["UPLOAD_DIR"], a.file_path), download_name=a.file_name)


def create_enquiry(f, seller, customer=None, linked_to=None):
    t = now()
    if not customer:
        customer = Customer(company=f["company"].strip(), company_key=company_key(f["company"]),
                            contact=f.get("contact", "").strip(), phone=f.get("phone", "").strip(),
                            phone_key=phone_key(f.get("phone")), email=f.get("email", "").strip(),
                            email_key=email_key(f.get("email")))
        db.session.add(customer)
        db.session.flush()
    kyc = new_kyc()
    kyc.update(need=bool(f.get("product")), qty=bool(f.get("qty")), location=bool(f.get("location")),
               repeat=is_repeat_customer(customer.id))
    e = Enquiry(enq_no=mint(seller.region, seller.code, t), customer_id=customer.id, received=t, last_update=t,
                source=f.get("source"), line=f.get("line"), type=f.get("type"), product=f["product"].strip(),
                location=f.get("location", "").strip(), qty=f.get("qty", "").strip(),
                date_needed=f.get("date_needed", "").strip(), pricing_deadline=f.get("pricing_deadline", "").strip(),
                region=seller.region, seller_code=seller.code, first_owner=seller.code, status="New", stage="New",
                kyc=kyc, red_flags=[], po={}, linked_to=linked_to)
    rescore(e)
    e.intake_score = e.score
    db.session.add(e)
    db.session.flush()
    log(f"Enquiry dicatat dari {e.source}{'. Terhubung ke pelanggan yang sudah ada' if linked_to else ''}. "
        f"Nomor {e.enq_no}.", current_user.name, e)
    post(region_channel(e.region), f"📥 Enquiry baru {e.enq_no}: {customer.company}, {e.product}. Pemilik {e.seller_code}.",
         action={"label": "Buka", "url": url_for("enquiries.detail", eid=e.id)})
    if seller.id != current_user.id:
        notify([seller], f"Enquiry baru untuk Anda: {e.enq_no} ({customer.company}).",
               url_for("enquiries.detail", eid=e.id))
    return e


@bp.route("/<int:eid>/kirim-ulang", methods=["POST"])
@login_required
def resend(eid):
    # boleh untuk enquiry region lain juga: hanya menambah catatan, tidak membuka datanya
    e = db.session.get(Enquiry, eid) or abort(404)
    if current_user.role not in ("sales", "rm", "admin"):
        abort(403)
    if not can_see(current_user, e):
        notify([seller_user(e.seller_code)], f"Kiriman ulang dari {e.customer.company} masuk lewat {current_user.name}.",
               url_for("enquiries.detail", eid=e.id))
    log(f"Kiriman ulang masuk via {request.form.get('source', '?')} ({request.form.get('product', '')}). "
        f"Dicatat sebagai duplikat, tanpa nomor baru.", current_user.name, e)
    db.session.commit()
    flash("Dicatat di enquiry yang sudah ada.", "ok")
    return redirect(url_for("enquiries.detail", eid=e.id) if can_see(current_user, e) else url_for("enquiries.index"))


# ---------------------------------------------------------------- detail
@bp.route("/<int:eid>")
@login_required
def detail(eid):
    e = get_enquiry(eid)
    acts = Activity.query.filter_by(enquiry_id=e.id).order_by(Activity.t.desc(), Activity.id.desc()).all()
    same = [x for x in recent_enquiries_of([e.customer]) if x.id != e.id]
    ch = enquiry_channel(e)
    db.session.commit()
    msgs = Message.query.filter_by(channel_id=ch.id).order_by(Message.id).all()
    reassign_to = [p for p in sellers_in_scope(current_user, e.region) if p.code != e.seller_code and p.region == e.region]
    revisions = [(f"Penawaran rev.{q.rev} ({q.tpl})", {"waiting": "menunggu RM", "sent": "terkirim", "rejected": "ditolak"}[q.status],
                  q.created_at) for q in e.quotes]
    revisions += [(f"{r.dept}{' urgent' if r.urgent else ''}", {"pending": "menunggu RM", "sent": "terkirim", "accepted": "dikerjakan",
                   "returned": "selesai", "rejected": "ditolak", "redirected": "ke katalog"}[r.status], r.sent_at)
                  for r in e.requests if r.dept in ("Drafter", "Estimator")]
    revisions.sort(key=lambda x: x[2] or e.received, reverse=True)
    dup_other = db.session.get(Enquiry, e.dup_review) if e.dup_review else None
    return render_template("enquiries/detail.html", e=e, s=sla(e), acts=acts, same=same, ch=ch, msgs=msgs,
                           clock=sla_clock(e), revisions=revisions, dup_other=dup_other,
                           quota=(urgent_used(e.seller_code, e.region), current_app.config["URGENT_QUOTA"]),
                           edit=can_edit(current_user, e), rm=is_rm_of(current_user, e.region),
                           STATUS=STATUS, LOSS=LOSS, NOT_PROSPECT=NOT_PROSPECT, DEPT_NAMES=DEPT_NAMES, DEPTS=DEPTS,
                           WON_STAGES=WON_STAGES, reassign_to=reassign_to)


# ---------------------------------------------------------------- aksi sales
@bp.route("/<int:eid>/kontak", methods=["POST"])
@login_required
def contacted(eid):
    e = get_enquiry(eid, edit=True)
    note = request.form.get("note", "").strip()
    if not note:
        return back(e, "Isi apa yang dibicarakan.", "bad")
    try:
        fname, fpath = save_upload(request.files.get("file"))
    except ValueError as exc:
        return back(e, str(exc), "bad")
    e.status, e.stage, e.contacted_at = "Contacted", "KYC", now()
    touch(e)
    proof = request.form.get("proof", "").strip()
    log(f"Kontak pertama via {request.form.get('how')}: {note}{' · bukti: ' + proof if proof else ''}", current_user.name, e,
        kind="contact", proof=bool(proof), file_name=fname, file_path=fpath)
    db.session.commit()
    return back(e, "Ditandai sudah dihubungi.")


@bp.route("/<int:eid>/status", methods=["POST"])
@login_required
def status(eid):
    e = get_enquiry(eid, edit=True)
    f = request.form
    st, note = f.get("status"), f.get("note", "").strip()
    if st not in STATUS or st == "New":
        abort(400)
    if not note:
        return back(e, "Komentar wajib diisi: apa yang ditunggu, apa yang berubah.", "bad")
    if st == "Lost" and f.get("loss") not in LOSS:
        return back(e, "Pilih alasan kalah.", "bad")
    if st == "Not prospectable" and f.get("close") not in NOT_PROSPECT:
        return back(e, "Pilih alasan tidak prospek.", "bad")
    e.status = st
    if not e.contacted_at:
        e.contacted_at = now()
    if st == "Lost":
        e.loss_reason = f["loss"]
    if st == "Not prospectable":
        e.close_reason = f["close"]
    if st == "Won" and e.stage not in WON_STAGES:
        e.stage = "PO received"
    if st == "Contacted" and e.stage in (None, "New"):
        e.stage = "KYC"
    touch(e)
    extra = f" ({e.loss_reason})" if st == "Lost" else f" ({e.close_reason})" if st == "Not prospectable" else ""
    log(f"Status: {st}{extra}. {note}", current_user.name, e)
    if st == "Won":
        post(region_channel(e.region), f"🎉 {e.enq_no} ({e.customer.company}) menang! Lanjut checklist PO.")
    db.session.commit()
    return back(e, "Status diperbarui.")


@bp.route("/<int:eid>/follow-up", methods=["POST"])
@login_required
def followup(eid):
    e = get_enquiry(eid, edit=True)
    note = request.form.get("note", "").strip()
    if not note:
        return back(e, "Isi catatan follow-up.", "bad")
    try:
        fname, fpath = save_upload(request.files.get("file"))
    except ValueError as exc:
        return back(e, str(exc), "bad")
    proof = request.form.get("proof", "").strip()
    touch(e)
    log(f"Follow-up: {note}{' · bukti: ' + proof if proof else ''}", current_user.name, e,
        kind="followup", proof=bool(proof), file_name=fname, file_path=fpath)
    db.session.commit()
    return back(e, "Follow-up dicatat." + ("" if (proof or fpath) else " Lampirkan bukti lain kali (screenshot WA/email)."))


@bp.route("/<int:eid>/kyc", methods=["POST"])
@login_required
def kyc(eid):
    e = get_enquiry(eid, edit=True)
    old, old_score, old_pc = dict(e.kyc or {}), e.score, e.price_check
    e.kyc = {k: (k in request.form) for k in KYC_KEYS}
    e.price_check = "price_check" in request.form
    rescore(e)
    changes = [f"{k} {'✓' if e.kyc[k] else '✗'}" for k in KYC_KEYS if bool(old.get(k)) != e.kyc[k]]
    if old_pc != e.price_check:
        changes.append("jalur cek harga " + ("aktif" if e.price_check else "nonaktif"))
    if changes:
        log(f"KYC diubah: {', '.join(changes)}. Skor {old_score} → {e.score}, tier {e.tier}.", current_user.name, e)
        db.session.commit()
    return back(e, "KYC disimpan." if changes else "Tidak ada perubahan.")


@bp.route("/<int:eid>/tanda-merah", methods=["POST"])
@login_required
def redflag(eid):
    e = get_enquiry(eid, edit=True)
    flags = list(e.red_flags or [])
    if request.form.get("remove") is not None:
        i = int(request.form["remove"])
        if 0 <= i < len(flags):
            gone = flags.pop(i)
            log(f"Tanda merah dihapus: {gone['reason']}.", current_user.name, e)
    else:
        reason = request.form.get("reason", "").strip()
        if not reason:
            return back(e, "Tanda merah wajib disertai alasan.", "bad")
        flags.append({"reason": reason, "who": current_user.name, "t": now().isoformat()})
        log(f"Tanda merah ditambah: {reason} (−10).", current_user.name, e)
    e.red_flags = flags
    rescore(e)
    db.session.commit()
    return back(e)


@bp.route("/<int:eid>/request", methods=["POST"])
@login_required
def send_request(eid):
    e = get_enquiry(eid, edit=True)
    f = request.form
    dept, title = f.get("dept"), f.get("title", "").strip()
    if dept not in DEPTS or not title:
        return back(e, "Pilih tim dan tulis kebutuhannya.", "bad")
    big = dept in ("Drafter", "Estimator")
    if big and not (e.kyc or {}).get("identity"):
        return back(e, f"Gerbang identitas: pastikan orang, perusahaan, dan kontaknya dulu sebelum minta ke {dept}.", "bad")
    if dept == "Drafter":
        if e.tier in ("C", "P"):
            return back(e, "Enquiry Tier C dan cek harga cukup pakai katalog.", "bad")
        if "catalog" not in f:
            return back(e, "Cek katalog dulu, lalu centang kotaknya.", "bad")
    urgent = "urgent" in f
    quota = current_app.config["URGENT_QUOTA"]
    if urgent and urgent_used(e.seller_code, e.region) >= quota:
        return back(e, f"Kuota request urgent minggu ini sudah habis ({quota} per sales). Kirim dengan lead time normal.", "bad")
    r = Request(enquiry_id=e.id, dept=dept, seller_code=e.seller_code, region=e.region, title=title, urgent=urgent,
                status="pending" if urgent else "sent", sent_at=now(), nudges=0)
    db.session.add(r)
    db.session.flush()
    log(f"Request dikirim ke {dept}{'. Urgent, menunggu persetujuan RM' if urgent else ''}.", current_user.name, request=r)
    if big:
        e.stage = dept
    if e.status == "Contacted":
        e.status = "Ongoing"
    touch(e)
    log(f"Request ke {dept}: {title}", current_user.name, e)
    if urgent:
        post(region_channel(e.region), f"🚨 Request urgent ke {dept} untuk {e.enq_no} dari {e.seller_code}: {title}",
             action={"label": "Setujui", "url": url_for("hub.approve", rid=r.id), "post": True, "roles": ["rm", "admin"]})
        notify(rms_of(e.region), f"Request urgent {dept} untuk {e.enq_no} menunggu persetujuan.", url_for("dash.region"))
    else:
        post(team_channel(dept), f"📨 Request baru {e.enq_no} (Tier {e.tier}, skor {e.score}) dari {e.seller_code}: {title}",
             action={"label": "Buka antrean", "url": url_for("hub.board")})
        notify(team_users(dept), f"Request baru dari {e.seller_code}: {e.enq_no}.", url_for("hub.board"))
    db.session.commit()
    return back(e, f"Request ke {dept} terkirim.")


@bp.route("/<int:eid>/buka-lagi", methods=["POST"])
@login_required
def reopen(eid):
    e = get_enquiry(eid, edit=True)
    e.status, e.loss_reason, e.close_reason = "Ongoing", None, None
    touch(e)
    log("Dibuka lagi: pelanggan kembali. Nomor tetap sama.", current_user.name, e)
    db.session.commit()
    return back(e, "Enquiry dibuka lagi.")


# ---------------------------------------------------------------- aksi RM
@bp.route("/<int:eid>/alihkan", methods=["POST"])
@login_required
def reassign(eid):
    e = get_enquiry(eid)
    if not is_rm_of(current_user, e.region):
        abort(403)
    to = User.query.filter_by(code=request.form.get("to")).first()
    reason = request.form.get("reason", "").strip() or "Belum dihubungi lebih dari 8 jam kerja"
    if not to or to.region != e.region or to.code == e.seller_code:
        return back(e, "Pilih sales tujuan di region yang sama.", "bad")
    old = e.seller_code
    e.first_owner = e.first_owner or old
    e.seller_code = to.code
    for r in e.requests:
        r.seller_code = to.code
    log(f"Dialihkan dari {old} ke {to.code}: {reason}. Nomor tetap.", current_user.name, e)
    notify([to], f"{e.enq_no} dialihkan ke Anda: {reason}.", url_for("enquiries.detail", eid=e.id))
    notify([seller_user(old)], f"{e.enq_no} dialihkan ke {to.code}.", url_for("enquiries.index"))
    db.session.commit()
    flash(f"Dialihkan ke {to.name}.", "ok")
    return redirect(request.form.get("next") or url_for("enquiries.detail", eid=e.id))


@bp.route("/<int:eid>/tutup-lost", methods=["POST"])
@login_required
def close_lost(eid):
    e = get_enquiry(eid)
    if not is_rm_of(current_user, e.region):
        abort(403)
    e.status, e.loss_reason = "Lost", "No response"
    touch(e)
    log("Ditutup sebagai Lost: tidak ada respons 7 hari. Bisa dibuka lagi.", current_user.name, e)
    db.session.commit()
    flash(f"{e.enq_no} ditutup sebagai Lost.", "ok")
    return redirect(request.form.get("next") or url_for("enquiries.detail", eid=e.id))


# ---------------------------------------------------------------- PO
@bp.route("/<int:eid>/po", methods=["POST"])
@login_required
def po(eid):
    e = get_enquiry(eid, edit=True)
    if e.stage != "PO received":
        abort(400)
    old = dict(e.po or {})
    e.po = {k: (k in request.form) for k, _ in PO_CHECK}
    e.po_number = request.form.get("po_number", "").strip() or None
    v = request.form.get("po_value", "").replace(".", "").replace(",", "").strip()
    e.po_value = int(v) if v.isdigit() else None
    changed = [k for k, _ in PO_CHECK if bool(old.get(k)) != e.po[k]]
    log(f"Checklist PO disimpan ({sum(e.po.values())}/{len(PO_CHECK)}"
        f"{', berubah: ' + ', '.join(changed) if changed else ''}). PO {e.po_number or '-'}.", current_user.name, e)
    db.session.commit()
    return back(e, "Checklist PO disimpan.")


@bp.route("/<int:eid>/po-kirim", methods=["POST"])
@login_required
def po_send(eid):
    e = get_enquiry(eid, edit=True)
    missing = [k for k, _ in PO_CHECK if not (e.po or {}).get(k)]
    if missing or not e.po_number or not e.po_value:
        return back(e, f"Checklist belum lengkap ({len(missing)} poin kurang) atau nomor/nilai PO kosong.", "bad")
    e.stage = "WO approval"
    touch(e)
    log("Paket serah-terima PO dikirim ke RM untuk disetujui.", current_user.name, e)
    post(region_channel(e.region), f"📦 Paket PO {e.enq_no} ({e.customer.company}) menunggu persetujuan RM.",
         action={"label": "Buka kontrol region", "url": url_for("dash.region")})
    notify(rms_of(e.region), f"Paket PO {e.enq_no} menunggu persetujuan.", url_for("dash.region"))
    db.session.commit()
    return back(e, "Paket PO dikirim ke RM.")


@bp.route("/<int:eid>/po-setujui", methods=["POST"])
@login_required
def po_approve(eid):
    e = get_enquiry(eid)
    if not is_rm_of(current_user, e.region) or e.stage != "WO approval":
        abort(403)
    e.stage = "WO / Kickoff"
    touch(e)
    log("Paket PO disetujui RM. Work order dan kickoff diminta ke Sales Support.", current_user.name, e)
    r = Request(enquiry_id=e.id, dept="Sales Support", seller_code=e.seller_code, region=e.region,
                title="Work order dan kickoff meeting", status="sent", sent_at=now(), nudges=0)
    db.session.add(r)
    db.session.flush()
    log("Work order dan kickoff diminta setelah persetujuan RM.", current_user.name, request=r)
    post(team_channel("Sales Support"), f"📨 Work order + kickoff untuk {e.enq_no} ({e.customer.company}).",
         action={"label": "Buka antrean", "url": url_for("hub.board")})
    notify([seller_user(e.seller_code)] + team_users("Sales Support"), f"PO {e.enq_no} disetujui RM.",
           url_for("enquiries.detail", eid=e.id))
    db.session.commit()
    flash("Paket PO disetujui, work order diminta.", "ok")
    return redirect(request.form.get("next") or url_for("enquiries.detail", eid=e.id))


@bp.route("/<int:eid>/tahap-berikut", methods=["POST"])
@login_required
def next_stage(eid):
    e = get_enquiry(eid, edit=True)
    i = WON_STAGES.index(e.stage) if e.stage in WON_STAGES else -1
    if i < 2 or i >= len(WON_STAGES) - 1:
        abort(400)
    e.stage = WON_STAGES[i + 1]
    touch(e)
    log(f"Tahap pindah ke {e.stage}.", current_user.name, e)
    db.session.commit()
    return back(e, f"Tahap: {e.stage}.")
