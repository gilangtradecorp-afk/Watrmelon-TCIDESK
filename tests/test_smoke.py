"""Tes asap: semua peran login, buka semua halaman, dan jalankan alur utama."""

import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from crm import create_app, db
from crm.models import Enquiry, Message, Notification, Quote, Request


@pytest.fixture()
def app():
    tmp = tempfile.mkdtemp()
    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False,
                      "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(tmp, "t.db"),
                      "UPLOAD_DIR": tmp, "DEMO_NOW": "2026-11-12T10:00:00+07:00"})
    with app.test_request_context():
        from seed import run
        run("demo12345")
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def login(c, u):
    c.post("/logout")
    r = c.post("/login", data={"username": u, "password": "demo12345"})
    assert r.status_code == 302, u


PAGES = {
    "adi": ["/meja", "/enquiry/", "/enquiry/?status=all", "/hub/", "/penawaran", "/beban-kerja", "/beban-kerja?p=today",
            "/daftar-harga", "/chat/", "/notifikasi", "/enquiry/baru", "/order"],
    "gil": ["/region", "/meja", "/enquiry/", "/hub/", "/penawaran", "/beban-kerja", "/beban-kerja?p=today&s=ADI",
            "/daftar-harga", "/chat/", "/admin/hari-libur", "/order", "/ekspor.xlsx"],
    "direktur": ["/manajemen", "/enquiry/", "/hub/", "/beban-kerja", "/daftar-harga", "/chat/", "/enquiry/?region=BPN",
                 "/order", "/ekspor.xlsx"],
    "drafter": ["/hub/", "/enquiry/", "/daftar-harga", "/chat/"],
    "admin": ["/manajemen", "/admin/pengguna", "/admin/hari-libur", "/region", "/chat/"],
}


def test_all_pages(app):
    c = app.test_client()
    for user, pages in PAGES.items():
        login(c, user)
        for p in pages:
            r = c.get(p, follow_redirects=True)
            assert r.status_code == 200, (user, p, r.status_code)
        with app.app_context():
            ids = [e.id for e in Enquiry.query.all()]
        for eid in ids:
            r = c.get(f"/enquiry/{eid}")
            assert r.status_code in (200, 403), (user, eid)
        r = c.get("/")
        assert r.status_code == 302


def test_scope(app):
    c = app.test_client()
    login(c, "adi")
    with app.app_context():
        other = Enquiry.query.filter(Enquiry.seller_code != "ADI").first().id
        bpn = Enquiry.query.filter_by(region="BPN").first().id
    assert c.get(f"/enquiry/{other}").status_code == 403
    assert c.get("/manajemen").status_code == 403
    login(c, "gil")
    assert c.get(f"/enquiry/{bpn}").status_code == 403


def test_flow(app):
    c = app.test_client()
    login(c, "adi")
    new = {"source": "WhatsApp", "seller": "ADI", "company": "PT Uji Coba", "contact": "Bu Rina",
           "phone": "0812 9999 1234", "product": "20ft office", "qty": "2", "location": "Sidoarjo",
           "line": "Container", "type": "Retail"}
    # aturan blokir: ADI punya enquiry yang belum dihubungi lewat 4 jam
    r = c.post("/enquiry/baru", data=new, follow_redirects=True)
    assert "Belum bisa ambil enquiry baru".encode() in r.data
    with app.app_context():
        blocked = Enquiry.query.filter_by(enq_no="ENQ-SBY-ADI-261111-0014").first().id
    c.post(f"/enquiry/{blocked}/kontak", data={"how": "WhatsApp", "note": "sudah", "file": (io.BytesIO(b"png"), "bukti.png")},
           content_type="multipart/form-data")
    with app.app_context():
        from crm.models import Activity
        a = Activity.query.filter_by(enquiry_id=blocked, kind="contact").first()
        assert a.has_proof and a.file_path
        aid = a.id
    assert c.get(f"/enquiry/aktivitas/{aid}/file").status_code == 200
    # buat enquiry baru
    r = c.post("/enquiry/baru", data=new)
    assert r.status_code == 302
    with app.app_context():
        e = Enquiry.query.filter(Enquiry.enq_no.like("ENQ-SBY-ADI-%")).order_by(Enquiry.id.desc()).first()
        assert e.customer.company == "PT Uji Coba" and not e.kyc["identity"]
        eid = e.id
        assert re.match(r"ENQ-SBY-ADI-\d{6}-0017$", e.enq_no), e.enq_no   # data contoh SBY sampai 0016
    # duplikat: nama tanpa PT dan beda format telepon
    r = c.post("/enquiry/baru", data={"source": "Direct email", "seller": "ADI", "company": "Uji Coba, PT", "product": "lagi"})
    assert b"sudah punya enquiry" in r.data
    # gerbang identitas
    r = c.post(f"/enquiry/{eid}/request", data={"dept": "Drafter", "title": "layout", "catalog": "on"}, follow_redirects=True)
    assert "Gerbang identitas".encode() in r.data
    # KYC + log
    c.post(f"/enquiry/{eid}/kyc", data={"identity": "on", "need": "on", "layout": "on", "qty": "on", "timeline": "on", "location": "on"})
    with app.app_context():
        e = db.session.get(Enquiry, eid)
        assert e.score == 75 and e.tier == "A"
    r = c.get(f"/enquiry/{eid}")
    assert "KYC diubah".encode() in r.data
    # kontak, request urgent
    c.post(f"/enquiry/{eid}/kontak", data={"how": "WhatsApp", "note": "sudah telepon"})
    c.post(f"/enquiry/{eid}/request", data={"dept": "Drafter", "title": "layout 2 unit", "catalog": "on", "urgent": "on"})
    with app.app_context():
        rq = Request.query.filter_by(enquiry_id=eid).first()
        assert rq.status == "pending"
        rid = rq.id
    # chat dengan mention
    with app.app_context():
        from crm.models import Channel
        ch = Channel.query.filter_by(key=f"enq:{eid}").first().id
    c.post(f"/chat/{ch}/kirim", data={"text": "Tolong cek @GIL"})
    # penawaran dengan diskon besar -> menunggu RM
    with app.app_context():
        from crm.models import CatalogItem
        cat = CatalogItem.query.filter_by(mode="Sale").first().id
    c.post(f"/enquiry/{eid}/penawaran", data={"tpl": "Sale", "save": "1", "cat0": cat, "qty0": "2", "discount": "10", "ppn": "11"})
    with app.app_context():
        q = Quote.query.filter_by(enquiry_id=eid).first()
        assert q.status == "waiting"
        qid = q.id
    assert c.get(f"/penawaran/{qid}.pdf").status_code == 200
    # RM menyetujui
    login(c, "gil")
    assert c.post(f"/hub/{rid}/setujui").status_code == 302
    assert c.post(f"/penawaran/{qid}/setujui").status_code == 302
    r = c.get("/notifikasi")
    assert "menyebut Anda".encode() in r.data
    # drafter menerima & mengembalikan
    login(c, "drafter")
    assert c.post(f"/hub/{rid}/terima").status_code == 302
    assert c.post(f"/hub/{rid}/kembalikan", data={"note": "gambar terlampir"}).status_code == 302
    with app.app_context():
        assert db.session.get(Request, rid).status == "returned"
        assert db.session.get(Enquiry, eid).stage == "Quote sent"
    # status lost wajib alasan
    login(c, "adi")
    r = c.post(f"/enquiry/{eid}/status", data={"status": "Lost", "note": "x"}, follow_redirects=True)
    assert "alasan kalah".encode() in r.data
    # kuota urgent: data contoh 1 + tes 1 = 2 (batas), yang ketiga ditolak
    r = c.post(f"/enquiry/{eid}/request", data={"dept": "Estimator", "title": "harga", "urgent": "on"}, follow_redirects=True)
    assert "Kuota request urgent".encode() in r.data
    # item custom tanpa harga -> request ke Estimator
    c.post(f"/enquiry/{eid}/penawaran", data={"tpl": "Sale", "save": "1", "custom0": "Pintu kaca custom", "qty0": "1"})
    with app.app_context():
        assert Request.query.filter(Request.enquiry_id == eid, Request.title.like("Harga item custom%")).count() == 1
    # SLA job jalan
    with app.test_request_context():
        from crm.sla_job import run_check
        assert run_check() > 0
        assert run_check() == 0   # tidak dobel
        assert Message.query.count() > 0


def test_cross_region_duplicate(app):
    c = app.test_client()
    login(c, "nov")
    base = {"source": "Direct email", "seller": "NOV", "company": "Bumi Konstruksi (sample)", "product": "Mess 40ft"}
    r = c.post("/enquiry/baru", data=base)
    assert "region SBY".encode() in r.data
    with app.app_context():
        other = Enquiry.query.filter_by(enq_no="ENQ-SBY-ADI-261111-0014").first()
        cid, oid = other.customer_id, other.id
    r = c.post("/enquiry/baru", data=dict(base, decision="linked", customer_id=cid, linked_to=oid))
    assert r.status_code == 302
    with app.app_context():
        e = Enquiry.query.filter_by(region="BPN", dup_review=oid).first()
        assert e is not None
        eid = e.id
    login(c, "hen")
    assert "Keputusan duplikat".encode() in c.get("/region").data
    c.post(f"/enquiry/{eid}/duplikat", data={"choice": "handover"})
    with app.app_context():
        e = db.session.get(Enquiry, eid)
        assert e.dup_review is None and e.status == "Not prospectable"
