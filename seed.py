"""Isi database kosong dengan akun dan data contoh (dari model Mas Gilang, seed_data.json).

Pakai:  .venv\\Scripts\\python -m flask --app run.py seed
        (password semua akun demo: demo123, ganti dengan --password ...)
"""

import json
import os
from datetime import date, datetime, timezone

from crm import db
from crm.models import (Activity, CatalogItem, Counter, Customer, Enquiry, Holiday, Quote, Request, User)
from crm.rules import KYC_KEYS, company_key, email_key, phone_key, kyc_score, tier
from crm.services import post, region_channel, team_channel

PEOPLE = [("GIL", "Gilang", "SBY", "rm"), ("ADI", "Adi", "SBY", "sales"), ("AND", "Andri", "SBY", "sales"),
          ("HEN", "Pak Hendy", "BPN", "rm"), ("NOV", "Novi", "BPN", "sales"), ("REV", "Revita", "BPN", "sales"),
          ("YUL", "Yulianti", "BPN", "sales"), ("DIN", "Dini", "JKT", "rm"), ("END", "Enda", "JKT", "sales"),
          ("EVI", "Evi", "JKT", "sales"), ("IVA", "Ivan", "JKT", "sales"), ("YOP", "Yopi", "JKT", "sales"),
          ("WEL", "Welly", "JKT", "sales")]
TEAMS = ["Drafter", "Estimator", "Purchasing", "Trucking", "Depo", "Branch", "Sales Support"]


def ts(s):
    return datetime.fromisoformat(s).astimezone(timezone.utc).replace(tzinfo=None) if s else None


def run(password="demo123"):
    if User.query.first():
        return "Database sudah berisi data. Hapus instance/crm.db dulu kalau mau mengisi ulang."
    with open(os.path.join(os.path.dirname(__file__), "seed_data.json"), encoding="utf-8") as f:
        d = json.load(f)

    users = []
    for code, name, region, role in PEOPLE:
        users.append(User(username=code.lower(), name=name, code=code, region=region, role=role))
    for t in TEAMS:
        users.append(User(username=t.lower().replace(" ", ""), name=f"Tim {t}", role="support", team=t))
    users += [User(username="direktur", name="Direktur", role="mgmt"), User(username="admin", name="Admin IT", role="admin")]
    for u in users:
        u.set_password(password)
        db.session.add(u)

    db.session.add_all([Holiday(day=date(2026, 12, 25), name="Hari Raya Natal"),
                        Holiday(day=date(2027, 1, 1), name="Tahun Baru Masehi")])

    cat_ids = {}
    for key, c in d["catalog"].items():
        item = CatalogItem(item=c["item"], category=c["category"], mode=c["mode"], price=c["price"], unit=c["unit"], active=True)
        db.session.add(item)
        db.session.flush()
        cat_ids[key] = item.id

    customers, enq_ids, counters = {}, {}, {}
    for key, e in sorted(d["enquiries"].items(), key=lambda kv: kv[1]["received"]):
        ck = company_key(e.get("customer")) or e.get("email") or key
        cust = customers.get(ck)
        if not cust:
            cust = Customer(company=e.get("customer") or "(tanpa nama perusahaan)", company_key=company_key(e.get("customer")),
                            contact=e.get("contact"), phone=e.get("phone"), phone_key=phone_key(e.get("phone")),
                            email=e.get("email"), email_key=email_key(e.get("email")))
            db.session.add(cust)
            db.session.flush()
            customers[ck] = cust
        kyc = {k: bool((e.get("kyc") or {}).get(k)) for k in KYC_KEYS}
        flags = [{"reason": "(data contoh)", "who": "System", "t": e["received"]}] * int(e.get("redFlags") or 0)
        score = kyc_score(kyc, len(flags))
        x = Enquiry(enq_no=e["enqNo"], customer_id=cust.id, received=ts(e["received"]), last_update=ts(e["lastUpdate"]),
                    contacted_at=ts(e.get("contactedAt")), source=e.get("source"), line=e.get("line"), type=e.get("type"),
                    product=e.get("product"), location=e.get("location"), qty=e.get("qty"),
                    date_needed=e.get("dateNeeded"), pricing_deadline=e.get("pricingDeadline"), region=e["region"],
                    seller_code=e["seller"], first_owner=e.get("firstOwner") or e["seller"], status=e["status"],
                    stage=e.get("stage") or "New", kyc=kyc, red_flags=flags, price_check=bool(e.get("priceCheck")),
                    score=score, intake_score=e.get("intakeScore", score), tier=tier(score, bool(e.get("priceCheck"))),
                    loss_reason=e.get("lossReason"), po=e.get("po") or {})
        db.session.add(x)
        db.session.flush()
        enq_ids[key] = x.id
        for a in e.get("log") or []:
            low = a["text"].lower()
            kind = "contact" if low.startswith(("first contact", "status: contacted")) else "followup" if low.startswith("follow") else None
            db.session.add(Activity(enquiry_id=x.id, t=ts(a["t"]), who=a["who"], text=a["text"], kind=kind,
                                    seller_code=x.seller_code, has_proof="proof" in low))
        q = e.get("quote")
        if q:
            lines = [{"item": l["item"], "unit": "", "qty": l["qty"], "price": l["price"]} for l in q["lines"]]
            db.session.add(Quote(enquiry_id=x.id, rev=q.get("rev", 1), tpl=q.get("tpl", "Sale"), lines=lines,
                                 subtotal=q["total"], discount_pct=0, ppn_pct=0, total=q["total"], status="sent",
                                 created_at=x.last_update, created_by=x.seller_code))
        parts = x.enq_no.split("-")
        k = (x.region, 2000 + int(parts[3][:2]))
        counters[k] = max(counters.get(k, 0), int(parts[4]))
    for (region, year), last in counters.items():
        db.session.add(Counter(region=region, year=year, last=last))

    for key, r in d["requests"].items():
        x = Request(enquiry_id=enq_ids[r["enqId"]], dept=r["dept"], seller_code=r["seller"], region=r["region"],
                    title=r["title"], urgent=bool(r.get("urgent")), status=r["status"], sent_at=ts(r["sentAt"]),
                    accepted_at=ts(r.get("acceptedAt")), due=ts(r.get("due")), returned_at=ts(r.get("returnedAt")),
                    nudges=r.get("nudges", 0), rm_approved=r["status"] not in ("pending",) and bool(r.get("urgent")))
        db.session.add(x)
        db.session.flush()
        for a in r.get("log") or []:
            db.session.add(Activity(request_id=x.id, t=ts(a["t"]), who=a["who"], text=a["text"]))

    for reg in ("SBY", "BPN", "JKT"):
        post(region_channel(reg), f"Selamat datang di channel region {reg}. Enquiry baru, pengingat SLA, dan persetujuan muncul di sini.")
    for t in TEAMS:
        post(team_channel(t), f"Channel tim {t}. Request baru dan pengingat request yang belum ditanggapi muncul di sini.")
    db.session.commit()
    return (f"Selesai: {len(users)} akun, {len(enq_ids)} enquiry, {len(d['requests'])} request, {len(cat_ids)} item harga. "
            f"Password semua akun demo: {password}")
