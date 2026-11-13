from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..models import Holiday, User
from ..rules import DEPT_NAMES, REGIONS, ROLES
from .auth import roles

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/pengguna", methods=["GET", "POST"])
@roles("admin")
def users():
    if request.method == "POST":
        f = request.form
        if f.get("id"):
            u = db.session.get(User, int(f["id"])) or abort(404)
            u.active = "active" in f
            if f.get("password"):
                if len(f["password"]) < 8:
                    flash("Password minimal 8 karakter.", "bad")
                    return redirect(url_for("admin.users"))
                u.set_password(f["password"])
            flash(f"{u.name} disimpan.", "ok")
        else:
            username = f.get("username", "").strip().lower()
            role = f.get("role")
            if not username or not f.get("name") or role not in ROLES or len(f.get("password", "")) < 8:
                flash("Isi username, nama, peran, dan password (min. 8 karakter).", "bad")
                return redirect(url_for("admin.users"))
            if User.query.filter_by(username=username).first():
                flash("Username sudah dipakai.", "bad")
                return redirect(url_for("admin.users"))
            code = f.get("code", "").strip().upper() or None
            if code and User.query.filter_by(code=code).first():
                flash("Kode sales sudah dipakai.", "bad")
                return redirect(url_for("admin.users"))
            u = User(username=username, name=f["name"].strip(), role=role, code=code if role in ("sales", "rm") else None,
                     region=f.get("region") if role in ("sales", "rm") else None,
                     team=f.get("team") if role == "support" else None, phone=f.get("phone", "").strip())
            u.set_password(f["password"])
            db.session.add(u)
            flash(f"{u.name} ditambahkan.", "ok")
        db.session.commit()
        return redirect(url_for("admin.users"))
    return render_template("admin_users.html", users=User.query.order_by(User.role, User.region, User.name).all(),
                           ROLES=ROLES, REGIONS=REGIONS, DEPT_NAMES=DEPT_NAMES)


@bp.route("/hari-libur", methods=["GET", "POST"])
@roles("admin", "rm")
def holidays():
    if request.method == "POST":
        if request.form.get("delete"):
            h = db.session.get(Holiday, int(request.form["delete"]))
            if h:
                db.session.delete(h)
        else:
            try:
                d = date.fromisoformat(request.form.get("day", ""))
            except ValueError:
                flash("Tanggal tidak valid.", "bad")
                return redirect(url_for("admin.holidays"))
            if not Holiday.query.filter_by(day=d).first():
                db.session.add(Holiday(day=d, name=request.form.get("name", "").strip() or "Libur"))
        db.session.commit()
        return redirect(url_for("admin.holidays"))
    return render_template("holidays.html", items=Holiday.query.order_by(Holiday.day).all())
