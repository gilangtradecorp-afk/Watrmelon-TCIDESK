import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-ganti-di-.env"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///" + os.path.join(BASE_DIR, "instance", "crm.db")
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 15}} if SQLALCHEMY_DATABASE_URI.startswith("sqlite") else {}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_DIR = os.path.join(BASE_DIR, "instance", "uploads")
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024
    PERMANENT_SESSION_LIFETIME = timedelta(hours=10)

    # Jam demo: isi misalnya 2026-11-12T10:00:00+07:00 supaya data contoh tetap "segar".
    DEMO_NOW = os.environ.get("CRM_DEMO_NOW", "")
    PPN_PCT = float(os.environ.get("CRM_PPN_PCT", "11"))
    DISCOUNT_LIMIT = float(os.environ.get("CRM_DISCOUNT_LIMIT", "5"))   # diskon di atas ini butuh RM
    QUOTE_VALID_DAYS = int(os.environ.get("CRM_QUOTE_VALID_DAYS", "14"))
    SLA_INTERVAL = int(os.environ.get("CRM_SLA_INTERVAL", "300"))       # detik antar pemeriksaan SLA
    URGENT_QUOTA = int(os.environ.get("CRM_URGENT_QUOTA", "2"))         # request urgent per sales per minggu
    BLOCK_ON_BREACH = os.environ.get("CRM_BLOCK_ON_BREACH", "1") == "1" # sales tidak bisa ambil enquiry baru
    PAYMENT_TERMS = os.environ.get("CRM_PAYMENT_TERMS", "DP 30%, pelunasan 70% sebelum pengiriman")
    DELIVERY_DAYS = int(os.environ.get("CRM_DELIVERY_DAYS", "10"))
