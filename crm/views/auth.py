from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .. import db
from ..models import Notification, User

bp = Blueprint("auth", __name__)

HOME = {"sales": "dash.desk", "rm": "dash.region", "mgmt": "dash.mgmt", "support": "hub.board", "admin": "dash.mgmt"}


def roles(*allowed):
    def deco(f):
        @wraps(f)
        @login_required
        def inner(*a, **kw):
            if current_user.role not in allowed:
                abort(403)
            return f(*a, **kw)
        return inner
    return deco


@bp.route("/")
@login_required
def index():
    return redirect(url_for(HOME[current_user.role]))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username", "").strip().lower()).first()
        if u and u.active and u.check_password(request.form.get("password", "")):
            login_user(u, remember=False)
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("auth.index"))
        flash("Username atau password salah.", "bad")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/password", methods=["GET", "POST"])
@login_required
def password():
    if request.method == "POST":
        if not current_user.check_password(request.form.get("old", "")):
            flash("Password lama salah.", "bad")
        elif len(request.form.get("new", "")) < 8:
            flash("Password baru minimal 8 karakter.", "bad")
        else:
            current_user.set_password(request.form["new"])
            db.session.commit()
            flash("Password diganti.", "ok")
            return redirect(url_for("auth.index"))
    return render_template("password.html")


@bp.route("/notifikasi")
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).limit(100).all()
    html = render_template("notifications.html", items=items)
    Notification.query.filter_by(user_id=current_user.id, read=False).update({"read": True})
    db.session.commit()
    return html


@bp.app_errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, msg="Anda tidak punya akses ke halaman atau aksi ini."), 403


@bp.app_errorhandler(404)
def notfound(_e):
    return render_template("error.html", code=404, msg="Halaman tidak ditemukan."), 404
