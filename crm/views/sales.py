"""Penawaran (Sale/Rental + PPN + diskon + PDF) dan daftar harga."""

import io
from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from .. import db
from ..models import Activity, CatalogItem, Enquiry, PriceChange, Quote, Request
from ..rules import PO_CHECK, WON_STAGES, to_local
from ..services import (can_see, enquiry_query, is_rm_of, log, notify, now, post, region_channel, request_query,
                        rms_of, seller_user, sla, team_channel, team_users, touch)
from .enquiries import get_enquiry

bp = Blueprint("sales", __name__)
LINE_ROWS = 8


def _num(v, default=0.0):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _int(v):
    v = str(v or "").replace(".", "").replace(",", "").strip()
    return int(v) if v.isdigit() else 0


def compute(lines, discount_pct, ppn_pct):
    subtotal = sum(l["qty"] * l["price"] for l in lines)
    after = round(subtotal * (1 - discount_pct / 100))
    return subtotal, after + round(after * ppn_pct / 100)


@bp.route("/penawaran")
@login_required
def quotes():
    rows = [e for e in enquiry_query(current_user).all() if e.quote]
    rows.sort(key=lambda e: e.quote.created_at or e.received, reverse=True)
    open_enq = [e for e in enquiry_query(current_user).all() if e.is_open]
    return render_template("quotes.html", rows=rows, open_enq=open_enq)


@bp.route("/enquiry/<int:eid>/penawaran", methods=["GET", "POST"])
@login_required
def build(eid):
    e = get_enquiry(eid, edit=True)
    cfg = current_app.config
    tpl = request.values.get("tpl", e.quote.tpl if e.quote else "Sale")
    items = CatalogItem.query.filter(CatalogItem.active.is_(True), CatalogItem.mode.in_((tpl, "Service"))).order_by(
        CatalogItem.category, CatalogItem.item).all()
    if request.method == "POST" and request.form.get("save"):
        f = request.form
        lines, unpriced = [], []
        for i in range(LINE_ROWS):
            qty = _int(f.get(f"qty{i}"))
            if not qty:
                continue
            if f.get(f"cat{i}"):
                c = db.session.get(CatalogItem, int(f[f"cat{i}"]))
                if c:
                    lines.append({"item": c.item, "unit": c.unit, "mode": c.mode, "qty": qty, "price": c.price})
            elif f.get(f"custom{i}", "").strip():
                if _int(f.get(f"price{i}")):
                    lines.append({"item": f[f"custom{i}"].strip() + " (custom)", "unit": "", "mode": tpl, "qty": qty,
                                  "price": _int(f.get(f"price{i}"))})
                else:
                    unpriced.append(f"{qty} x {f[f'custom{i}'].strip()}")
        if unpriced:
            r = Request(enquiry_id=e.id, dept="Estimator", seller_code=e.seller_code, region=e.region,
                        title="Harga item custom untuk penawaran: " + "; ".join(unpriced), status="sent", sent_at=now(), nudges=0)
            db.session.add(r)
            db.session.flush()
            log("Request harga item custom dikirim dari pembuat penawaran.", current_user.name, request=r)
            log(f"Request ke Estimator: harga item custom ({'; '.join(unpriced)}).", current_user.name, e)
            post(team_channel("Estimator"), f"📨 Harga item custom untuk {e.enq_no} dari {e.seller_code}: {'; '.join(unpriced)}",
                 action={"label": "Buka antrean", "url": url_for("hub.board")})
            notify(team_users("Estimator"), f"Harga item custom diminta untuk {e.enq_no}.", url_for("hub.board"))
            db.session.commit()
            flash("Item custom tanpa harga dikirim ke Estimator. Buat penawaran lagi setelah harganya kembali.", "warn")
            return redirect(url_for("enquiries.detail", eid=e.id))
        if not lines:
            flash("Tambahkan minimal satu baris.", "bad")
        else:
            disc = max(0.0, min(100.0, _num(f.get("discount"))))
            ppn = max(0.0, _num(f.get("ppn"), cfg["PPN_PCT"]))
            sub, total = compute(lines, disc, ppn)
            rev = (e.quote.rev if e.quote else 0) + 1
            needs_rm = disc > cfg["DISCOUNT_LIMIT"] and not is_rm_of(current_user, e.region)
            q = Quote(enquiry_id=e.id, rev=rev, tpl=tpl, lines=lines, subtotal=sub, discount_pct=disc, ppn_pct=ppn,
                      total=total, rental_months=_int(f.get("months")) or None if tpl == "Rental" else None,
                      deposit=_int(f.get("deposit")) or None if tpl == "Rental" else None,
                      valid_until=(to_local(now(), e.tz) + timedelta(days=cfg["QUOTE_VALID_DAYS"])).date(),
                      payment_terms=f.get("payment_terms", "").strip() or cfg["PAYMENT_TERMS"],
                      delivery_days=_int(f.get("delivery_days")) or None,
                      status="waiting" if needs_rm else "sent", created_at=now(), created_by=current_user.name)
            db.session.add(q)
            if needs_rm:
                log(f"Penawaran rev.{rev} ({tpl}) dibuat, diskon {disc:g}% di atas batas {cfg['DISCOUNT_LIMIT']:g}%: "
                    f"menunggu RM.", current_user.name, e)
                db.session.flush()
                post(region_channel(e.region), f"💸 Penawaran {e.enq_no} rev.{rev} diskon {disc:g}% menunggu persetujuan RM.",
                     action={"label": "Buka kontrol region", "url": url_for("dash.region")})
                notify(rms_of(e.region), f"Penawaran {e.enq_no} rev.{rev} butuh persetujuan diskon.", url_for("dash.region"))
                flash("Diskon di atas batas: penawaran menunggu persetujuan RM.", "warn")
            else:
                mark_sent(e, q)
                flash("Penawaran disimpan dan ditandai terkirim.", "ok")
            db.session.commit()
            return redirect(url_for("enquiries.detail", eid=e.id))
    return render_template("quote_build.html", e=e, tpl=tpl, items=items, rows=range(LINE_ROWS),
                           ppn=cfg["PPN_PCT"], limit=cfg["DISCOUNT_LIMIT"], valid=cfg["QUOTE_VALID_DAYS"],
                           terms=cfg["PAYMENT_TERMS"], delivery=cfg["DELIVERY_DAYS"])


def mark_sent(e, q):
    e.stage, e.status = "Quote sent", "Ongoing"
    if not e.contacted_at:
        e.contacted_at = now()
    touch(e)
    log(f"Penawaran rev.{q.rev} ({q.tpl}) terkirim: Rp {q.total:,}".replace(",", ".") + ".", current_user.name, e)


@bp.route("/penawaran/<int:qid>/setujui", methods=["POST"])
@login_required
def approve(qid):
    q = db.session.get(Quote, qid) or abort(404)
    if not is_rm_of(current_user, q.enquiry.region) or q.status != "waiting":
        abort(403)
    q.status, q.approved_by = "sent", current_user.name
    mark_sent(q.enquiry, q)
    log(f"Diskon {q.discount_pct:g}% di rev.{q.rev} disetujui RM.", current_user.name, q.enquiry)
    notify([seller_user(q.enquiry.seller_code)], f"Diskon penawaran {q.enquiry.enq_no} disetujui.",
           url_for("enquiries.detail", eid=q.enquiry_id))
    db.session.commit()
    flash("Penawaran disetujui.", "ok")
    return redirect(url_for("dash.region"))


@bp.route("/penawaran/<int:qid>/tolak", methods=["POST"])
@login_required
def reject(qid):
    q = db.session.get(Quote, qid) or abort(404)
    if not is_rm_of(current_user, q.enquiry.region) or q.status != "waiting":
        abort(403)
    q.status = "rejected"
    log(f"Diskon {q.discount_pct:g}% di rev.{q.rev} ditolak RM. Buat revisi baru.", current_user.name, q.enquiry)
    notify([seller_user(q.enquiry.seller_code)], f"Diskon penawaran {q.enquiry.enq_no} ditolak RM.",
           url_for("enquiries.detail", eid=q.enquiry_id))
    db.session.commit()
    flash("Penawaran ditolak.", "ok")
    return redirect(url_for("dash.region"))


@bp.route("/penawaran/<int:qid>.pdf")
@login_required
def pdf(qid):
    q = db.session.get(Quote, qid) or abort(404)
    e = q.enquiry
    if not can_see(current_user, e):
        abort(403)
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    rp = lambda n: "Rp " + f"{round(n):,}".replace(",", ".")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm)
    ss = getSampleStyleSheet()
    flow = [Paragraph("<b>PT TRADECORP</b>", ss["Title"]),
            Paragraph(f"Penawaran {'Penjualan' if q.tpl == 'Sale' else 'Sewa'} · {e.enq_no} · Rev.{q.rev}", ss["Heading3"]),
            Spacer(1, 4 * mm),
            Paragraph(f"Kepada: <b>{e.customer.company}</b><br/>{e.customer.contact or ''}<br/>{e.location or ''}", ss["Normal"]),
            Spacer(1, 4 * mm)]
    data = [["No", "Item", "Jml", "Harga satuan", "Jumlah"]]
    for i, l in enumerate(q.lines, 1):
        data.append([i, Paragraph(f"{l['item']}<br/><font size=8>{l.get('unit') or ''}</font>", ss["Normal"]),
                     l["qty"], rp(l["price"]), rp(l["qty"] * l["price"])])
    after = round(q.subtotal * (1 - q.discount_pct / 100))
    data += [["", "Subtotal", "", "", rp(q.subtotal)]]
    if q.discount_pct:
        data += [["", f"Diskon {q.discount_pct:g}%", "", "", "- " + rp(q.subtotal - after)]]
    data += [["", f"PPN {q.ppn_pct:g}%", "", "", rp(q.total - after)], ["", "TOTAL", "", "", rp(q.total)]]
    t = Table(data, colWidths=[10 * mm, 85 * mm, 14 * mm, 32 * mm, 33 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, len(q.lines)), 0.4, colors.grey),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                           ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    flow += [t, Spacer(1, 5 * mm)]
    terms = [f"Berlaku sampai {q.valid_until:%d-%m-%Y}." if q.valid_until else "",
             f"Pembayaran: {q.payment_terms}." if q.payment_terms else "",
             f"Pengiriman: {q.delivery_days} hari kerja setelah DP diterima." if q.delivery_days else ""]
    if q.tpl == "Rental":
        terms.append(f"Periode sewa: {q.rental_months or '-'} bulan. Deposit: {rp(q.deposit or 0)}. "
                     "Unit dikembalikan dalam kondisi baik; kerusakan ditagihkan.")
    flow.append(Paragraph("<br/>".join(x for x in terms if x), ss["Normal"]))
    flow.append(Spacer(1, 10 * mm))
    flow.append(Paragraph(f"Hormat kami,<br/><br/><br/>{q.created_by}", ss["Normal"]))
    doc.build(flow)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", download_name=f"{e.enq_no}-rev{q.rev}.pdf")


# ---------------------------------------------------------------- order (PO)
@bp.route("/order")
@login_required
def orders():
    rows = [e for e in enquiry_query(current_user).all() if e.status == "Won"]
    rows.sort(key=lambda e: (WON_STAGES.index(e.stage) if e.stage in WON_STAGES else 0, e.last_update))
    return render_template("orders.html", rows=rows, WON_STAGES=WON_STAGES, n_check=len(PO_CHECK))


# ---------------------------------------------------------------- ekspor Excel
@bp.route("/ekspor.xlsx")
@login_required
def export():
    if current_user.role not in ("rm", "mgmt", "admin"):
        abort(403)
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from ..rules import fmt_hours

    E = enquiry_query(current_user).all()
    loc = lambda t: to_local(t, current_user.tz).replace(tzinfo=None) if t else None
    wb = Workbook()
    ws = wb.active
    ws.title = "Enquiry"
    ws.append(["Nomor", "Region", "Sales", "Pemilik awal", "Diterima", "Sumber", "Pelanggan", "Kontak", "Lini", "Tipe",
               "Produk", "Lokasi", "Jumlah", "Status", "Tahap", "Tier", "Skor", "Skor awal", "Kontak pertama",
               "SLA", "Alasan kalah", "Alasan tidak prospek", "Penawaran terakhir (Rp)", "Nomor PO", "Nilai PO (Rp)",
               "Update terakhir"])
    for e in E:
        s = sla(e)
        ws.append([e.enq_no, e.region, e.seller_code, e.first_owner, loc(e.received), e.source, e.customer.company,
                   e.customer.contact, e.line, e.type, e.product, e.location, e.qty, e.status, e.stage, e.tier, e.score,
                   e.intake_score, loc(e.contacted_at), s["t"] if e.is_open else "", e.loss_reason, e.close_reason,
                   e.quote.total if e.quote else None, e.po_number, e.po_value, loc(e.last_update)])
    ws2 = wb.create_sheet("Request")
    ws2.append(["Nomor ENQ", "Region", "Sales", "Tim", "Kebutuhan", "Urgent", "Status", "Dikirim", "Diterima",
                "Target", "Selesai", "Colekan", "Alasan"])
    for r in request_query(current_user).all():
        ws2.append([r.enquiry.enq_no, r.region, r.seller_code, r.dept, r.title, "Ya" if r.urgent else "", r.status,
                    loc(r.sent_at), loc(r.accepted_at), loc(r.due), loc(r.returned_at), r.nudges, r.reason])
    ws3 = wb.create_sheet("Penawaran")
    ws3.append(["Nomor ENQ", "Rev", "Template", "Subtotal", "Diskon %", "PPN %", "Total", "Status", "Dibuat", "Oleh"])
    for e in E:
        for q in e.quotes:
            ws3.append([e.enq_no, q.rev, q.tpl, q.subtotal, q.discount_pct, q.ppn_pct, q.total, q.status,
                        loc(q.created_at), q.created_by])
    for sheet in (ws, ws2, ws3):
        for c in sheet[1]:
            c.font = Font(bold=True)
        sheet.freeze_panes = "A2"
        for col in sheet.columns:
            width = max(len(str(c.value or "")) for c in col[:200])
            sheet.column_dimensions[col[0].column_letter].width = min(45, max(10, width + 2))
            for c in col[1:]:
                if hasattr(c.value, "hour"):
                    c.number_format = "dd-mm-yyyy hh:mm"
                elif isinstance(c.value, int) and c.value > 100000:
                    c.number_format = "#,##0"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    scope = current_user.region or "semua-region"
    return send_file(buf, download_name=f"crm-{scope}-{to_local(now(), current_user.tz):%Y%m%d}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------- daftar harga
@bp.route("/daftar-harga", methods=["GET", "POST"])
@login_required
def catalog():
    can_edit = current_user.role in ("rm", "admin")
    if request.method == "POST":
        if not can_edit:
            abort(403)
        f = request.form
        if f.get("id"):
            c = db.session.get(CatalogItem, int(f["id"])) or abort(404)
            new = _int(f.get("price"))
            if new and new != c.price:
                db.session.add(PriceChange(item_id=c.id, old=c.price, new=new, t=now(), who=current_user.name))
                c.price = new
            c.active = "active" in f
            c.updated_at, c.updated_by = now(), current_user.name
            flash(f"{c.item} disimpan.", "ok")
        else:
            if not f.get("item", "").strip() or not _int(f.get("price")) or f.get("mode") not in ("Sale", "Rental", "Service"):
                flash("Isi nama item, mode, dan harga.", "bad")
                return redirect(url_for("sales.catalog"))
            c = CatalogItem(item=f["item"].strip(), category=f.get("category", "").strip(), mode=f["mode"],
                            price=_int(f["price"]), unit=f.get("unit", "").strip(), active=True,
                            updated_at=now(), updated_by=current_user.name)
            db.session.add(c)
            flash(f"{c.item} ditambahkan.", "ok")
        db.session.commit()
        return redirect(url_for("sales.catalog"))
    items = CatalogItem.query.order_by(CatalogItem.mode, CatalogItem.category, CatalogItem.item).all()
    hist = PriceChange.query.order_by(PriceChange.id.desc()).limit(30).all()
    names = {c.id: c.item for c in items}
    return render_template("catalog.html", items=items, hist=hist, names=names, can_edit=can_edit)
