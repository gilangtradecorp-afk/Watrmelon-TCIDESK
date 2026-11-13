"""Chat tim internal: channel region, channel tim, thread per enquiry, pesan langsung."""

import os
import uuid

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_file,
                   url_for)
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.utils import secure_filename

from .. import db
from ..models import Channel, Enquiry, Message, ReadMark, User
from ..rules import DEPT_NAMES, REGIONS
from ..services import can_see_channel, channel, enquiry_query, post, region_channel, team_channel

bp = Blueprint("chat", __name__, url_prefix="/chat")
ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".xlsx", ".xls", ".docx", ".doc", ".dwg", ".zip"}


def base_channels(u):
    """Channel region & tim yang memang milik user (dibuat kalau belum ada)."""
    keys = []
    if u.role in ("mgmt", "admin"):
        keys += [region_channel(r) for r in REGIONS] + [team_channel(d) for d in DEPT_NAMES]
    elif u.role == "rm":
        keys += [region_channel(u.region)] + [team_channel(d) for d in DEPT_NAMES]
    elif u.role == "sales":
        keys += [region_channel(u.region)]
    elif u.role == "support":
        keys += [team_channel(u.team)]
    return keys


def visible_channels(u):
    chans = base_channels(u)
    db.session.commit()
    ids = {c.id for c in chans}
    # thread enquiry yang sudah ada pesannya & DM milik user
    q = Channel.query.filter(Channel.kind.in_(("enq", "dm"))).all()
    enq_ids = {str(e.id) for e in enquiry_query(u).all()} if u.role not in ("mgmt", "admin") else None
    for c in q:
        if c.id in ids:
            continue
        if c.kind == "dm" and str(u.id) in c.key.split(":")[1:]:
            chans.append(c)
        elif c.kind == "enq" and (enq_ids is None or c.ref in enq_ids):
            if Message.query.filter_by(channel_id=c.id).first():
                chans.append(c)
    return chans


def unread_map(u, chans):
    if not chans:
        return {}
    marks = {m.channel_id: m.last_id for m in ReadMark.query.filter_by(user_id=u.id).all()}
    rows = db.session.query(Message.channel_id, func.count(Message.id)).filter(
        Message.channel_id.in_([c.id for c in chans])).group_by(Message.channel_id).all()
    out = {}
    for cid, _n in rows:
        last = marks.get(cid, 0)
        out[cid] = Message.query.filter(Message.channel_id == cid, Message.id > last,
                                        (Message.user_id.is_(None)) | (Message.user_id != u.id)).count()
    return out


def unread_total(u):
    try:
        chans = visible_channels(u)
        return sum(unread_map(u, chans).values())
    except Exception:
        db.session.rollback()
        return 0


def mark_read(u, c):
    last = db.session.query(func.max(Message.id)).filter_by(channel_id=c.id).scalar() or 0
    m = db.session.get(ReadMark, (u.id, c.id))
    if not m:
        db.session.add(ReadMark(user_id=u.id, channel_id=c.id, last_id=last))
    else:
        m.last_id = max(m.last_id or 0, last)
    db.session.commit()


def get_channel(cid):
    c = db.session.get(Channel, cid) or abort(404)
    if not can_see_channel(current_user, c):
        abort(403)
    return c


def can_post(u, c):
    return can_see_channel(u, c) and not (u.role == "mgmt" and c.kind != "dm")


@bp.route("/")
@login_required
def home():
    chans = visible_channels(current_user)
    first = chans[0] if chans else None
    return redirect(url_for("chat.room", cid=first.id)) if first else render_template("chat.html", chans=[], c=None)


@bp.route("/<int:cid>")
@login_required
def room(cid):
    c = get_channel(cid)
    chans = visible_channels(current_user)
    if c not in chans:
        chans.append(c)
    unread = unread_map(current_user, chans)
    msgs = Message.query.filter_by(channel_id=c.id).order_by(Message.id.desc()).limit(200).all()[::-1]
    mark_read(current_user, c)
    people = User.query.filter(User.active.is_(True), User.id != current_user.id).order_by(User.name).all()
    enq = db.session.get(Enquiry, int(c.ref)) if c.kind == "enq" else None
    return render_template("chat.html", chans=chans, c=c, msgs=msgs, unread=unread, people=people, enq=enq,
                           can_post=can_post(current_user, c), dm_name=dm_name)


def dm_name(c, u):
    if c.kind != "dm":
        return c.name
    ids = [int(x) for x in c.key.split(":")[1:]]
    other = next((i for i in ids if i != u.id), u.id)
    o = db.session.get(User, other)
    return "@ " + (o.name if o else "?")


@bp.route("/<int:cid>/baru")
@login_required
def poll(cid):
    c = get_channel(cid)
    after = request.args.get("after", 0, type=int)
    msgs = Message.query.filter(Message.channel_id == c.id, Message.id > after).order_by(Message.id).all()
    if msgs:
        mark_read(current_user, c)
    return jsonify(last=msgs[-1].id if msgs else after,
                   html="".join(render_template("_message.html", m=m) for m in msgs))


@bp.route("/<int:cid>/kirim", methods=["POST"])
@login_required
def send(cid):
    c = get_channel(cid)
    if not can_post(current_user, c):
        abort(403)
    text = request.form.get("text", "").strip()
    up = request.files.get("file")
    fname = fpath = None
    if up and up.filename:
        ext = os.path.splitext(up.filename)[1].lower()
        if ext not in ALLOWED:
            flash("Jenis file tidak diizinkan.", "bad")
            return redirect(request.form.get("next") or url_for("chat.room", cid=c.id))
        fname = secure_filename(up.filename) or "file" + ext
        fpath = f"{uuid.uuid4().hex}{ext}"
        up.save(os.path.join(current_app.config["UPLOAD_DIR"], fpath))
    if not text and not fname:
        return redirect(request.form.get("next") or url_for("chat.room", cid=c.id))
    post(c, text or "(lampiran)", current_user, file_name=fname, file_path=fpath)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True)
    nxt = request.form.get("next", "")
    return redirect(nxt if nxt.startswith("/") else url_for("chat.room", cid=c.id))


@bp.route("/file/<int:mid>")
@login_required
def file(mid):
    m = db.session.get(Message, mid) or abort(404)
    if not m.file_path or not can_see_channel(current_user, m.channel):
        abort(404)
    return send_file(os.path.join(current_app.config["UPLOAD_DIR"], m.file_path), download_name=m.file_name)


@bp.route("/dm", methods=["POST"])
@login_required
def dm():
    other = db.session.get(User, request.form.get("user", type=int)) or abort(404)
    a, b = sorted([current_user.id, other.id])
    c = channel(f"dm:{a}:{b}", f"DM {a}-{b}", "dm")
    db.session.commit()
    return redirect(url_for("chat.room", cid=c.id))
