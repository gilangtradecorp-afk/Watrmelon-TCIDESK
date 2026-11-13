import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    if dbapi_conn.__class__.__module__.startswith("sqlite3"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object("config.Config")
    if overrides:
        app.config.update(overrides)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
        os.makedirs(os.path.dirname(app.config["SQLALCHEMY_DATABASE_URI"][10:]), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Silakan login dulu."
    csrf.init_app(app)

    from . import models  # noqa: F401
    from .views import auth, enquiries, dash, hub, sales, chat, admin
    for bp in (auth.bp, enquiries.bp, dash.bp, hub.bp, sales.bp, chat.bp, admin.bp):
        app.register_blueprint(bp)

    from . import filters
    filters.register(app)

    from . import cli
    cli.register(app)

    with app.app_context():
        db.create_all()
    return app
