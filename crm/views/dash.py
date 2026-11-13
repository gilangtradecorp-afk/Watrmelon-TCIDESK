from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from datetime import datetime, timedelta

from ..models import Enquiry, Quote, Request
from ..rules import (DEPT_NAMES, LOSS, NOT_PROSPECT, OPEN, REGIONS, SOURCES, STATUS, TIER_ORDER, biz_hours, to_local,
                     tz_of)
from ..services import (enquiry_query, holidays, next_action, now, proof_rate, request_query, rms_of, rstate,
                        sellers_in_scope, sla, urgent_used)
from flask import current_app
from .auth import roles
from .enquiries import sort_key

bp = Blueprint("dash", __name__)


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def first_contact(e):
    return biz_hours(e.received, e.contacted_at, e.tz, holidays()) if e.contacted_at else None


def local_day(t, region="SBY"):
    return to_local(t, tz_of(region)).date()


def this_month(t):
    a, b = local_day(t), local_day(now())
    return (a.year, a.month) == (b.year, b.month) and t <= now()


def is_today(t):
    return local_day(t) == local_day(now())


def dept_bars(reqs):
    rows = []
    for d in DEPT_NAMES:
        a = [r for r in reqs if r.dept == d]
        c = {"done": 0, "open": 0, "late": 0}
        for r in a:
            c[rstate(r)["b"]] += 1
        rows.append((d, len(a), c))
    mx = max([1] + [n for _, n, _ in rows])
    return rows, mx


def quote_value(e):
    return e.quote.total if e.quote else 0


def recent(t, days):
    return t is not None and (now() - t).days < days


def win_rate_90(E):
    closed = [e for e in E if e.status in ("Won", "Lost") and recent(e.last_update, 90)]
    won = [e for e in closed if e.status == "Won"]
    return len(won), len(closed) - len(won), sum((e.po_value or quote_value(e)) for e in won)


def fc_30(E):
    return avg([first_contact(e) for e in E if recent(e.received, 30)])


def due_label(due):
    if not due:
        return "", ""
    n = now()
    if due < n:
        return "Telat", "bad"
    a, b = local_day(due), local_day(n)
    if a == b:
        return f"Hari ini {to_local(due, tz_of('SBY')):%H:%M}", "warn"
    if (a - b).days == 1:
        return "Besok", "ok"
    return f"{a.day}/{a.month}", "ok"


@bp.route("/meja")
@roles("sales", "rm", "admin")
def desk():
    E = [e for e in enquiry_query(current_user).all() if e.seller_code == current_user.code] if current_user.role != "sales" \
        else enquiry_query(current_user).all()
    R = [r for r in request_query(current_user).all() if r.seller_code == current_user.code]
    op = [e for e in E if e.is_open]
    S = {e.id: sla(e) for e in op}
    tiers = {"A": 0, "B": 0, "C": 0, "P": 0}
    for e in op:
        tiers[e.tier] += 1
    won, lost, won_value = win_rate_90(E)
    bars, mx = dept_bars([r for r in R if this_month(r.sent_at)])
    acts = {e.id: next_action(e) for e in op}
    labels = {eid: due_label(d) for eid, (_, d) in acts.items()}
    order = sorted(op, key=lambda e: (0 if S[e.id]["bad"] else 1, TIER_ORDER.get(e.tier, 9),
                                      acts[e.id][1] or datetime.max))
    from .enquiries import blocking_breaches
    return render_template("desk.html", op=order, S=S, tiers=tiers, acts=acts, labels=labels, won_value=won_value,
                           blocked=bool(blocking_breaches(current_user)),
                           breaches=[e for e in op if S[e.id]["k"] in ("breach", "reassign")],
                           overdue=sum(S[e.id]["k"] == "overdue" for e in op),
                           follow=sum(S[e.id]["k"] == "followup" for e in op),
                           today=sum(is_today(e.received) for e in E), mtd=sum(this_month(e.received) for e in E),
                           fc=fc_30(E), won=won, lost=lost, bars=bars, mx=mx, sla=sla)


@bp.route("/region")
@roles("rm", "admin")
def region():
    reg = current_user.region or request.args.get("r", "SBY")
    E = Enquiry.query.filter_by(region=reg).all()
    R = Request.query.filter_by(region=reg).all()
    op = [e for e in E if e.is_open]
    S = {e.id: sla(e) for e in op}
    m = [e for e in E if this_month(e.received)]
    team = []
    for p in sellers_in_scope(current_user, reg):
        pe = [e for e in E if e.seller_code == p.code]
        po = [e for e in pe if e.is_open]
        b = sum(S[e.id]["bad"] for e in po)
        wn, ls, _v = win_rate_90(pe)
        pr, pt = proof_rate(p.code)
        team.append(dict(p=p, open=len(po), fc=fc_30(pe), breaches=b, wn=wn, ls=ls, proof=(pr, pt),
                         overdue=sum(S[e.id]["k"] in ("overdue", "followup") for e in po),
                         urgent=urgent_used(p.code, reg)))
    quotes_waiting = [q for q in Quote.query.filter_by(status="waiting").all() if q.enquiry.region == reg]
    sellers = sellers_in_scope(current_user, reg)
    quotes_out = [e for e in op if e.stage == "Quote sent"]
    won = [e for e in E if e.status == "Won"]
    return render_template("region.html", reg=reg, E=E, op=op, S=S, m=m, team=team, sellers=sellers,
                           quotes_out_value=sum(quote_value(e) for e in quotes_out),
                           won_value=sum((e.po_value or quote_value(e)) for e in won),
                           breaches=sorted([e for e in op if S[e.id]["bad"]], key=sort_key),
                           to_reassign=[e for e in op if S[e.id]["k"] == "reassign"],
                           autolost=[e for e in op if S[e.id]["k"] == "autolost"],
                           urgent=[r for r in R if r.status == "pending"],
                           po_wait=[e for e in E if e.stage == "WO approval"],
                           quotes_waiting=quotes_waiting, SOURCES=SOURCES,
                           dup_reviews=[e for e in E if e.dup_review], quota=current_app.config["URGENT_QUOTA"],
                           urgent_used=lambda code: urgent_used(code, reg),
                           quotes_out=quotes_out, won=won, sla=sla)


@bp.route("/beban-kerja")
@roles("sales", "rm", "mgmt", "admin")
def workload():
    reg = request.args.get("region", "") if current_user.role in ("mgmt", "admin") else ""
    period = "today" if request.args.get("p") == "today" else "mtd"
    in_period = is_today if period == "today" else this_month
    E = enquiry_query(current_user).all()
    R = [r for r in request_query(current_user).all() if in_period(r.sent_at)]
    if reg:
        E = [e for e in E if e.region == reg]
        R = [r for r in R if r.region == reg]
    sellers = sellers_in_scope(current_user, reg or None)
    seller_f = request.args.get("s", "")
    all_sellers = sellers
    if seller_f:
        sellers = [p for p in sellers if p.code == seller_f]
        E = [e for e in E if e.seller_code == seller_f]
        R = [r for r in R if r.seller_code == seller_f]
    n_local = local_day(now())
    month_days = []
    for d in range(1, n_local.day + 1):
        cnt = sum(1 for e in E if local_day(e.received) == n_local.replace(day=d))
        month_days.append((d, cnt))
    day_max = max([1] + [c for _, c in month_days])
    st = {r.id: rstate(r) for r in R}
    nf = sorted([r for r in R if st[r.id]["nofb"]], key=lambda r: -st[r.id]["h"])
    resp = {}
    for d in DEPT_NAMES:
        a = [r for r in R if r.dept == d]
        resp[d] = dict(n=len(a), done=sum(st[r.id]["b"] == "done" for r in a),
                       prog=sum(st[r.id]["b"] != "done" and not st[r.id]["nofb"] for r in a),
                       nofb=sum(st[r.id]["nofb"] for r in a), nudges=sum(r.nudges or 0 for r in a),
                       first=avg([biz_hours(r.sent_at, r.accepted_at or r.returned_at, tz_of(r.region), holidays())
                                  for r in a if r.accepted_at or r.returned_at]))
    bars, mx = dept_bars(R)
    nf_ids = {r.id for r in nf}
    per = {}
    for p in sellers:
        a = [e for e in E if e.seller_code == p.code]
        o = [e for e in a if e.is_open]
        mine = [r for r in R if r.seller_code == p.code]
        per[p.code] = dict(today=sum(is_today(e.received) for e in a), mtd=sum(this_month(e.received) for e in a),
                           open=len(o), tier_a=sum(e.tier == "A" for e in o), total=len(mine),
                           dept={d: (sum(r.dept == d for r in mine), sum(r.dept == d and r.id in nf_ids for r in mine))
                                 for d in DEPT_NAMES})
    return render_template("workload.html", R=R, sellers=sellers, st=st, nf=nf, resp=resp, bars=bars, mx=mx,
                           reg=reg, per=per, today_count=sum(is_today(e.received) for e in E),
                           mtd_count=sum(this_month(e.received) for e in E), period=period, seller_f=seller_f,
                           all_sellers=all_sellers, month_days=month_days, day_max=day_max, today_day=n_local.day,
                           late=sum(st[r.id]["b"] == "late" for r in R))


@bp.route("/manajemen")
@roles("mgmt", "admin")
def mgmt():
    E = Enquiry.query.all()
    op = [e for e in E if e.is_open]
    S = {e.id: sla(e) for e in op}
    m = [e for e in E if this_month(e.received)]
    rows = []
    for r in REGIONS:
        a = [e for e in E if e.region == r]
        wn = [e for e in a if e.status == "Won"]
        w90, ls, _v = win_rate_90(a)
        b = [e for e in a if e.is_open and S[e.id]["bad"]]
        rm = rms_of(r)
        rm_codes = {u.code for u in rm}
        rows.append(dict(r=r, name=REGIONS[r][0], rm=", ".join(u.name for u in rm) or "–",
                         mtd=sum(this_month(e.received) for e in a),
                         tier_a=sum(this_month(e.received) and e.tier == "A" for e in a),
                         fc=fc_30(a), quotes=sum(1 for e in a if e.quote),
                         wn=w90, ls=ls, po_value=sum((e.po_value or quote_value(e)) for e in wn),
                         b_sales=sum(e.seller_code not in rm_codes for e in b), b_rm=sum(e.seller_code in rm_codes for e in b)))
    pipeline = {t: {"n": 0, "v": 0} for t in ("A", "B", "C", "P")}
    for e in op:
        pipeline[e.tier]["n"] += 1
        pipeline[e.tier]["v"] += quote_value(e)
    stages = {}
    for e in op:
        s = stages.setdefault(e.stage, {"n": 0, "v": 0})
        s["n"] += 1
        s["v"] += quote_value(e)
    lost = [e for e in E if e.status == "Lost" and recent(e.last_update, 90)]
    loss = sorted([(l, sum(e.loss_reason == l for e in lost)) for l in LOSS], key=lambda x: -x[1])
    np_ = [e for e in E if e.status == "Not prospectable"]
    nprs = [(l, sum(e.close_reason == l for e in np_)) for l in NOT_PROSPECT]
    src = [(s, sum(e.source == s for e in m)) for s in SOURCES]
    won = [e for e in E if e.status == "Won"]
    return render_template("mgmt.html", E=E, op=op, m=m, rows=rows, pipeline=pipeline, stages=stages, loss=loss,
                           nprs=nprs, src=src, fc=fc_30(E), lost_n=len(lost),
                           breaches=sum(S[e.id]["bad"] for e in op),
                           quotes_out=[e for e in op if e.stage == "Quote sent"], won=won, qv=quote_value,
                           won_value=sum((e.po_value or quote_value(e)) for e in won))
