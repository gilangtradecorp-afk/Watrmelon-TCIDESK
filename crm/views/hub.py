from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .. import db
from ..models import Activity, Request
from ..rules import DEPT_NAMES, DEPTS, REJECT_REASONS, add_biz_days, tz_of
from ..services import (can_act_request, enquiry_channel, holidays, is_rm_of, log, notify, now, post,
                        request_query, rstate, seller_user, team_channel, team_users, touch)

bp = Blueprint("hub", __name__, url_prefix="/hub")


def get_req(rid):
    return db.session.get(Request, rid) or abort(404)


def done(msg, cat="ok"):
    flash(msg, cat)
    nxt = request.form.get("next", "")
    return redirect(nxt if nxt.startswith("/") else url_for("hub.board"))


@bp.route("/")
@login_required
def board():
    rows = request_query(current_user).all()
    region = request.args.get("region", "")
    if region and current_user.role in ("mgmt", "admin"):
        rows = [r for r in rows if r.region == region]
    states = {r.id: rstate(r) for r in rows}
    active = [r for r in rows if states[r.id]["b"] != "done"]
    depts = [current_user.team] if current_user.role == "support" else DEPT_NAMES
    lanes = {d: sorted([r for r in active if r.dept == d], key=lambda r: -(r.enquiry.score or 0)) for d in depts}
    cap = {}
    for d in ("Drafter", "Estimator"):
        acc = Request.query.filter_by(dept=d, status="accepted").all()
        by = {}
        for r in acc:
            by[r.region] = by.get(r.region, 0) + 1
        cap[d] = dict(used=len(acc), cap=DEPTS[d][1], by=by, tier_a=sum(1 for r in acc if r.enquiry.tier == "A"))
    return render_template("hub.html", lanes=lanes, states=states, cap=cap, region=region,
                           redirected=sum(1 for r in rows if r.status == "redirected"),
                           rejected=sum(1 for r in rows if r.status == "rejected"),
                           can_act=lambda r: can_act_request(current_user, r), REJECT_REASONS=REJECT_REASONS)


@bp.route("/<int:rid>/log")
@login_required
def history(rid):
    r = get_req(rid)
    if r not in request_query(current_user).all() and current_user.role not in ("mgmt", "admin"):
        abort(403)
    acts = Activity.query.filter_by(request_id=r.id).order_by(Activity.t.desc(), Activity.id.desc()).all()
    return render_template("request_log.html", r=r, acts=acts, st=rstate(r))


@bp.route("/<int:rid>/terima", methods=["POST"])
@login_required
def accept(rid):
    r = get_req(rid)
    if not can_act_request(current_user, r) or r.status != "sent":
        abort(403)
    days = DEPTS[r.dept][0]
    r.status, r.accepted_at = "accepted", now()
    r.due = add_biz_days(now(), days, tz_of(r.region), holidays())
    log(f"Diterima {r.dept} oleh {current_user.name}. Target {days} hari kerja.", current_user.name, request=r)
    post(enquiry_channel(r.enquiry), f"✅ {r.dept} menerima request: {r.title[:100]}", current_user)
    notify([seller_user(r.seller_code)], f"{r.dept} menerima request {r.enquiry.enq_no}.", url_for("enquiries.detail", eid=r.enquiry_id))
    db.session.commit()
    return done("Request diterima.")


@bp.route("/<int:rid>/kembalikan", methods=["POST"])
@login_required
def hand_back(rid):
    r = get_req(rid)
    if not can_act_request(current_user, r) or r.status != "accepted":
        abort(403)
    note = request.form.get("note", "").strip()
    if not note:
        return done("Tulis apa yang dikembalikan (gambar, harga, jadwal, jawaban).", "bad")
    r.status, r.returned_at = "returned", now()
    log(f"Dikembalikan: {note}", current_user.name, request=r)
    log(f"{r.dept} mengembalikan: {note}", current_user.name, r.enquiry)
    post(enquiry_channel(r.enquiry), f"📬 {r.dept} mengembalikan hasil: {note}", current_user)
    notify([seller_user(r.seller_code)], f"{r.dept} sudah mengembalikan {r.enquiry.enq_no}.", url_for("enquiries.detail", eid=r.enquiry_id))
    db.session.commit()
    return done("Dikembalikan ke sales.")


@bp.route("/<int:rid>/tolak", methods=["POST"])
@login_required
def reject(rid):
    r = get_req(rid)
    if not can_act_request(current_user, r) or r.status != "sent":
        abort(403)
    reason, note = request.form.get("reason"), request.form.get("note", "").strip()
    if reason not in REJECT_REASONS or not note:
        return done("Pilih alasan dan tulis apa yang harus diperbaiki sales.", "bad")
    r.status, r.reason, r.returned_at = "rejected", reason, now()
    log(f"Ditolak ({reason}): {note}", current_user.name, request=r)
    post(enquiry_channel(r.enquiry), f"↩️ {r.dept} menolak request ({reason}): {note}", current_user)
    notify([seller_user(r.seller_code)], f"{r.dept} menolak request {r.enquiry.enq_no}: {reason}.", url_for("enquiries.detail", eid=r.enquiry_id))
    db.session.commit()
    return done("Request ditolak.")


@bp.route("/<int:rid>/ke-katalog", methods=["POST"])
@login_required
def to_catalog(rid):
    r = get_req(rid)
    if not can_act_request(current_user, r) or r.status != "sent" or r.dept != "Drafter":
        abort(403)
    r.status, r.returned_at = "redirected", now()
    log("Dialihkan ke katalog gambar: desain standar sudah cocok.", current_user.name, request=r)
    post(enquiry_channel(r.enquiry), "📚 Drafter: desain standar di katalog sudah cocok, tidak perlu gambar baru.", current_user)
    notify([seller_user(r.seller_code)], f"Request Drafter {r.enquiry.enq_no} dialihkan ke katalog.", url_for("enquiries.detail", eid=r.enquiry_id))
    db.session.commit()
    return done("Dialihkan ke katalog.")


@bp.route("/<int:rid>/colek", methods=["POST"])
@login_required
def nudge(rid):
    r = get_req(rid)
    if current_user.role not in ("sales", "rm", "admin") or r not in request_query(current_user).all():
        abort(403)
    r.nudges = (r.nudges or 0) + 1
    log("Colekan terkirim: mohon konfirmasi status.", current_user.name, request=r)
    post(team_channel(r.dept), f"👋 {current_user.name} menanyakan status request {r.enquiry.enq_no}: {r.title[:100]}", current_user)
    notify(team_users(r.dept), f"{current_user.name} menanyakan request {r.enquiry.enq_no}.", url_for("hub.board"))
    db.session.commit()
    return done("Colekan dikirim ke tim.")


@bp.route("/<int:rid>/setujui", methods=["POST"])
@login_required
def approve(rid):
    r = get_req(rid)
    if not is_rm_of(current_user, r.region) or r.status != "pending":
        abort(403)
    r.status, r.rm_approved, r.sent_at = "sent", True, now()
    log(f"Request urgent disetujui RM ({current_user.name}). Dikirim ke {r.dept}.", current_user.name, request=r)
    post(team_channel(r.dept), f"🚨 Request URGENT {r.enquiry.enq_no} (disetujui RM): {r.title}",
         action={"label": "Buka antrean", "url": url_for("hub.board")})
    notify(team_users(r.dept) + [seller_user(r.seller_code)], f"Request urgent {r.enquiry.enq_no} disetujui RM.", url_for("hub.board"))
    db.session.commit()
    return done("Request urgent disetujui.")


@bp.route("/<int:rid>/tolak-urgent", methods=["POST"])
@login_required
def reject_urgent(rid):
    r = get_req(rid)
    if not is_rm_of(current_user, r.region) or r.status != "pending":
        abort(403)
    r.status, r.reason, r.returned_at = "rejected", "Urgent tidak disetujui", now()
    log("Request urgent tidak disetujui RM. Kirim ulang dengan lead time normal.", current_user.name, request=r)
    notify([seller_user(r.seller_code)], f"Request urgent {r.enquiry.enq_no} tidak disetujui RM.", url_for("enquiries.detail", eid=r.enquiry_id))
    db.session.commit()
    return done("Request urgent ditolak.")
