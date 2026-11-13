from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, login_manager
from .rules import REGIONS, DEFAULT_TZ, OPEN, tz_of


def utcnow_real():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    code = db.Column(db.String(8), unique=True)          # kode sales di nomor ENQ
    role = db.Column(db.String(10), nullable=False)      # sales / rm / mgmt / support / admin
    region = db.Column(db.String(4))                     # SBY / BPN / JKT
    team = db.Column(db.String(20))                      # untuk tim support
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def is_active(self):
        return self.active

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def tz(self):
        return tz_of(self.region) if self.region else DEFAULT_TZ

    @property
    def label(self):
        return f"{self.name} ({self.code})" if self.code else self.name


@login_manager.user_loader
def _load_user(uid):
    return db.session.get(User, int(uid))


class Holiday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)


class Counter(db.Model):
    """Nomor urut ENQ per region per tahun."""
    region = db.Column(db.String(4), primary_key=True)
    year = db.Column(db.Integer, primary_key=True)
    last = db.Column(db.Integer, default=0, nullable=False)


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(120), nullable=False)
    company_key = db.Column(db.String(120), index=True)
    contact = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    phone_key = db.Column(db.String(20), index=True)
    email = db.Column(db.String(120))
    email_key = db.Column(db.String(120), index=True)
    created_at = db.Column(db.DateTime, default=utcnow_real)


class Enquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enq_no = db.Column(db.String(40), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    customer = db.relationship("Customer", backref="enquiries")
    received = db.Column(db.DateTime, nullable=False)
    last_update = db.Column(db.DateTime, nullable=False)
    contacted_at = db.Column(db.DateTime)
    source = db.Column(db.String(20))
    line = db.Column(db.String(20))
    type = db.Column(db.String(20))
    product = db.Column(db.String(200))
    location = db.Column(db.String(120))
    qty = db.Column(db.String(40))
    date_needed = db.Column(db.String(40))
    pricing_deadline = db.Column(db.String(40))
    region = db.Column(db.String(4), nullable=False, index=True)
    seller_code = db.Column(db.String(8), nullable=False, index=True)
    first_owner = db.Column(db.String(8))
    status = db.Column(db.String(20), default="New", index=True)
    stage = db.Column(db.String(20), default="New")
    kyc = db.Column(db.JSON, default=dict)
    red_flags = db.Column(db.JSON, default=list)          # [{reason, who, t}]
    price_check = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=0)
    intake_score = db.Column(db.Integer, default=0)
    tier = db.Column(db.String(1), default="C")
    loss_reason = db.Column(db.String(40))
    close_reason = db.Column(db.String(60))               # alasan Not prospectable
    po = db.Column(db.JSON, default=dict)
    po_number = db.Column(db.String(60))
    po_value = db.Column(db.BigInteger)
    linked_to = db.Column(db.Integer)                     # enquiry lain dari pelanggan sama
    dup_review = db.Column(db.Integer)                    # enquiry region lain yang perlu diputuskan RM

    quotes = db.relationship("Quote", backref="enquiry", order_by="Quote.rev.desc()")
    requests = db.relationship("Request", backref="enquiry", order_by="Request.sent_at.desc()")

    @property
    def is_open(self):
        return self.status in OPEN

    @property
    def tz(self):
        return tz_of(self.region)

    @property
    def quote(self):
        return self.quotes[0] if self.quotes else None

    @property
    def red_flag_count(self):
        return len(self.red_flags or [])


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enquiry_id = db.Column(db.Integer, db.ForeignKey("enquiry.id"), index=True)
    request_id = db.Column(db.Integer, db.ForeignKey("request.id"), index=True)
    t = db.Column(db.DateTime, nullable=False)
    who = db.Column(db.String(80))
    text = db.Column(db.Text, nullable=False)
    kind = db.Column(db.String(12))                       # contact / followup (untuk % bukti)
    seller_code = db.Column(db.String(8))
    has_proof = db.Column(db.Boolean, default=False)
    file_name = db.Column(db.String(200))
    file_path = db.Column(db.String(200))


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enquiry_id = db.Column(db.Integer, db.ForeignKey("enquiry.id"), nullable=False, index=True)
    dept = db.Column(db.String(20), nullable=False, index=True)
    seller_code = db.Column(db.String(8), nullable=False)
    region = db.Column(db.String(4), nullable=False)
    title = db.Column(db.Text, nullable=False)
    urgent = db.Column(db.Boolean, default=False)
    rm_approved = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(12), default="sent", index=True)  # pending/sent/accepted/returned/rejected/redirected
    sent_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime)
    due = db.Column(db.DateTime)
    returned_at = db.Column(db.DateTime)
    reason = db.Column(db.String(200))
    nudges = db.Column(db.Integer, default=0)


class CatalogItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(40))
    mode = db.Column(db.String(10), nullable=False)       # Sale / Rental / Service
    price = db.Column(db.BigInteger, nullable=False)
    unit = db.Column(db.String(40))
    active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime)
    updated_by = db.Column(db.String(80))


class PriceChange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("catalog_item.id"), index=True)
    old = db.Column(db.BigInteger)
    new = db.Column(db.BigInteger)
    t = db.Column(db.DateTime)
    who = db.Column(db.String(80))


class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enquiry_id = db.Column(db.Integer, db.ForeignKey("enquiry.id"), nullable=False, index=True)
    rev = db.Column(db.Integer, nullable=False)
    tpl = db.Column(db.String(10), nullable=False)        # Sale / Rental
    lines = db.Column(db.JSON, default=list)              # [{item, qty, price}]
    subtotal = db.Column(db.BigInteger, default=0)
    discount_pct = db.Column(db.Float, default=0)
    ppn_pct = db.Column(db.Float, default=0)
    total = db.Column(db.BigInteger, default=0)
    rental_months = db.Column(db.Integer)
    deposit = db.Column(db.BigInteger)
    valid_until = db.Column(db.Date)
    payment_terms = db.Column(db.String(200))
    delivery_days = db.Column(db.Integer)
    status = db.Column(db.String(12), default="sent")     # waiting (butuh RM) / sent / rejected
    created_at = db.Column(db.DateTime)
    created_by = db.Column(db.String(80))
    approved_by = db.Column(db.String(80))


# ---------------------------------------------------------------- chat tim
class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False)   # region:SBY, team:Drafter, enq:12, dm:3:7
    name = db.Column(db.String(80), nullable=False)
    kind = db.Column(db.String(10), nullable=False)               # region / team / enq / dm
    ref = db.Column(db.String(20))                                # SBY / Drafter / enquiry id


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channel.id"), nullable=False, index=True)
    channel = db.relationship("Channel")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User")
    t = db.Column(db.DateTime, nullable=False)
    text = db.Column(db.Text, nullable=False)
    action = db.Column(db.JSON)          # {"label":..., "url":..., "roles":[...]}
    file_name = db.Column(db.String(200))
    file_path = db.Column(db.String(200))


class ReadMark(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channel.id"), primary_key=True)
    last_id = db.Column(db.Integer, default=0)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    t = db.Column(db.DateTime, nullable=False)
    text = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(200))
    read = db.Column(db.Boolean, default=False, index=True)


class SlaAlert(db.Model):
    """Penanda pengingat SLA yang sudah dikirim, supaya tidak dobel."""
    key = db.Column(db.String(80), primary_key=True)
    t = db.Column(db.DateTime)


__all__ = ["User", "Holiday", "Counter", "Customer", "Enquiry", "Activity", "Request", "CatalogItem",
           "PriceChange", "Quote", "Channel", "Message", "ReadMark", "Notification", "SlaAlert", "REGIONS"]
