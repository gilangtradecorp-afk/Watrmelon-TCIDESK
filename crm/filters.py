from flask_login import current_user

from .rules import DEFAULT_TZ, KYC, PO_CHECK, ROLES, REGIONS, fmt_hours, to_local

MON = "Jan Feb Mar Apr Mei Jun Jul Agu Sep Okt Nov Des".split()


def _tz():
    try:
        return current_user.tz if current_user.is_authenticated else DEFAULT_TZ
    except Exception:
        return DEFAULT_TZ


def dt(value, with_time=True):
    if not value:
        return "–"
    loc = to_local(value, _tz())
    s = f"{loc.day} {MON[loc.month - 1]}"
    return f"{s} {loc:%H:%M}" if with_time else s


def day(value):
    if not value:
        return "–"
    return f"{value.day} {MON[value.month - 1]} {value.year}"


def rp(n):
    return "Rp " + f"{round(n or 0):,}".replace(",", ".")


def rps(n):
    n = n or 0
    if n >= 1e9:
        return f"Rp {n / 1e9:.1f} M".replace(".", ",")
    if n >= 1e6:
        return f"Rp {round(n / 1e6)} jt"
    return rp(n)


def pct(a, b):
    return f"{round(a / b * 100)}%" if b else "–"


def wa_text(e, q):
    """Pesan WhatsApp ringkas untuk penawaran yang sudah terkirim."""
    lines = [f"Yth. {e.customer.contact or e.customer.company},", "",
             f"Berikut penawaran {'penjualan' if q.tpl == 'Sale' else 'sewa'} kami ({e.enq_no} rev.{q.rev}):"]
    for l in q.lines:
        lines.append(f"- {l['qty']} x {l['item']} @ {rp(l['price'])}")
    if q.discount_pct:
        lines.append(f"Diskon {q.discount_pct:g}%")
    lines.append(f"Total {rp(q.total)}{' termasuk PPN ' + format(q.ppn_pct, 'g') + '%' if q.ppn_pct else ''}")
    if q.tpl == "Rental" and q.rental_months:
        lines.append(f"Periode sewa {q.rental_months} bulan, deposit {rp(q.deposit or 0)}")
    if q.payment_terms:
        lines.append(f"Pembayaran: {q.payment_terms}")
    if q.delivery_days:
        lines.append(f"Pengiriman: {q.delivery_days} hari kerja setelah DP")
    if q.valid_until:
        lines.append(f"Berlaku sampai {day(q.valid_until)}")
    lines += ["", "PDF lengkap kami kirim terpisah. Terima kasih."]
    return "\n".join(lines)


def register(app):
    app.jinja_env.filters.update(dt=dt, day=day, rp=rp, rps=rps, hrs=fmt_hours)
    from .services import rstate, sla
    app.jinja_env.globals.update(pct=pct, KYC=KYC, PO_CHECK=PO_CHECK, ROLES=ROLES, REGIONS=REGIONS, sla=sla, rstate=rstate, wa_text=wa_text)

    @app.context_processor
    def _nav():
        if not current_user.is_authenticated:
            return {}
        from .views.chat import unread_total
        from .models import Notification
        r = current_user.role
        nav = {
            "sales": [("dash.desk", "Meja saya"), ("enquiries.index", "Enquiry"), ("hub.board", "Request saya"),
                      ("sales.quotes", "Penawaran"), ("sales.orders", "Order (PO)"), ("dash.workload", "Beban kerja"), ("sales.catalog", "Daftar harga")],
            "rm": [("dash.region", "Kontrol region"), ("enquiries.index", "Enquiry"), ("hub.board", "Hand-off Hub"),
                   ("sales.quotes", "Penawaran"), ("sales.orders", "Order (PO)"), ("dash.workload", "Beban kerja"),
                   ("sales.catalog", "Daftar harga"), ("dash.desk", "Meja saya")],
            "mgmt": [("dash.mgmt", "Semua region"), ("enquiries.index", "Enquiry"), ("sales.orders", "Order (PO)"), ("hub.board", "Hand-off Hub"),
                     ("dash.workload", "Beban kerja"), ("sales.catalog", "Daftar harga")],
            "support": [("hub.board", "Antrean tim"), ("enquiries.index", "Enquiry terkait"), ("sales.catalog", "Daftar harga")],
            "admin": [("dash.mgmt", "Semua region"), ("enquiries.index", "Enquiry"), ("sales.orders", "Order (PO)"), ("hub.board", "Hand-off Hub"),
                      ("dash.workload", "Beban kerja"), ("sales.catalog", "Daftar harga"), ("admin.users", "Pengguna"),
                      ("admin.holidays", "Hari libur")],
        }[r]
        bell = Notification.query.filter_by(user_id=current_user.id, read=False).count()
        return {"NAV": nav, "BELL": bell, "CHAT_UNREAD": unread_total(current_user)}
