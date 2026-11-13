"""Pemeriksaan SLA terjadwal: kirim pengingat ke chat tim + notifikasi, sekali per kejadian."""

import threading
import time

from flask import url_for

from . import db
from .models import Enquiry, Request, SlaAlert
from .rules import OPEN, to_local, tz_of
from .services import (enquiry_channel, notify, now, post, region_channel, rms_of, rstate, seller_user,
                       sla, team_channel, team_users)


def _once(key):
    if db.session.get(SlaAlert, key):
        return False
    db.session.add(SlaAlert(key=key, t=now()))
    return True


def run_check():
    sent = 0
    today = to_local(now(), tz_of("SBY")).date().isoformat()
    for e in Enquiry.query.filter(Enquiry.status.in_(OPEN)).all():
        s = sla(e)
        link = url_for("enquiries.detail", eid=e.id)
        seller = seller_user(e.seller_code)
        who = f"{e.enq_no} ({e.customer.company})"
        if s["k"] == "breach" and _once(f"enq:{e.id}:breach"):
            post(enquiry_channel(e), f"⏰ Pengingat: {who}: {s['t']}. Batas kontak pertama 4 jam kerja.")
            notify([seller], f"{who} belum dihubungi ({s['t']}).", link)
            sent += 1
        elif s["k"] == "reassign" and _once(f"enq:{e.id}:reassign"):
            post(region_channel(e.region), f"⚠️ {who} milik {e.seller_code} belum dihubungi lebih dari 8 jam kerja. RM bisa mengalihkan.",
                 action={"label": "Buka enquiry", "url": link})
            notify(rms_of(e.region) + [seller], f"{who} perlu dialihkan: {s['t']}.", link)
            sent += 1
        elif s["k"] == "overdue" and _once(f"enq:{e.id}:overdue:{today}"):
            post(enquiry_channel(e), f"⏰ Status {who} belum di-update 3 hari kerja.")
            notify([seller], f"Update status {who}: {s['t']}.", link)
            sent += 1
        elif s["k"] == "followup" and _once(f"enq:{e.id}:follow:{today}"):
            post(enquiry_channel(e), f"⏰ Penawaran {who} sudah terkirim, follow-up hari ini belum dicatat.")
            notify([seller], f"Follow-up harian {who} belum dicatat.", link)
            sent += 1
        elif s["k"] == "autolost" and _once(f"enq:{e.id}:autolost"):
            post(region_channel(e.region), f"🔕 {who} tidak ada respons 7 hari. Usul ditutup sebagai Lost.",
                 action={"label": "Buka kontrol region", "url": url_for("dash.region")})
            notify(rms_of(e.region), f"{who} diam 7 hari, usul tutup sebagai Lost.", url_for("dash.region"))
            sent += 1

    for r in Request.query.filter(Request.status.in_(("sent", "accepted"))).all():
        st = rstate(r)
        e = r.enquiry
        link = url_for("hub.board")
        who = f"{r.dept} untuk {e.enq_no}"
        if st["nofb"] and _once(f"req:{r.id}:nofb"):
            post(team_channel(r.dept), f"⏰ Request {e.enq_no} dari {r.seller_code} belum ditanggapi 4 jam kerja: {r.title[:120]}",
                 action={"label": "Buka antrean", "url": link})
            notify(team_users(r.dept), f"Request {who} belum ditanggapi.", link)
            sent += 1
        if st["rm"] and _once(f"req:{r.id}:rmflag"):
            post(region_channel(r.region), f"⚠️ Request {who} belum ditanggapi 1 hari kerja.",
                 action={"label": "Buka antrean", "url": link})
            notify(rms_of(r.region), f"Request {who} belum ditanggapi 1 hari kerja.", link)
            sent += 1
        if st["b"] == "late" and _once(f"req:{r.id}:late"):
            post(enquiry_channel(e), f"⏰ Request {r.dept} melewati target.")
            notify([seller_user(r.seller_code)] + team_users(r.dept), f"Request {who} telat dari target.", link)
            sent += 1
    db.session.commit()
    return sent


def start_background(app):
    interval = app.config["SLA_INTERVAL"]

    def loop():
        while True:
            try:
                with app.test_request_context():
                    n = run_check()
                    if n:
                        print(f"[SLA] {n} pengingat dikirim")
            except Exception as exc:  # pemeriksaan tidak boleh mematikan server
                print("[SLA] gagal:", exc)
            time.sleep(interval)

    threading.Thread(target=loop, name="sla-check", daemon=True).start()
