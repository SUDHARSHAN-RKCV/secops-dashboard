# app/__init__.py
import os
from pathlib import Path
from flask import Flask,render_template,current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv
from app.main import health
from app.models import db, User
from app.config import POSTGRES_URI, DBTYPE
import psycopg2
from datetime import datetime
from urllib.parse import urlparse
load_dotenv()

login_manager = LoginManager()
secret_key = os.getenv("session_secret_key")

# Global constant for file manager base path
BASE_DIR = Path(__file__).resolve().parent / "static" / "sources"
cached_data = {}
cached_chart_data = []

def is_db_reachable(db_uri):
    try:
        parsed = urlparse(db_uri)
        conn = psycopg2.connect(
            dbname=parsed.path[1:],  # strip leading slash
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432,
            connect_timeout=3
        )
        conn.close()
        return True
    except Exception:
        return False
    
PG_DMZ_URI = os.getenv("POSTGRES_URI")
PG_LOCAL_URI = os.getenv("POSTGRES_local_URI")

if is_db_reachable(PG_DMZ_URI):
    PGURI = PG_DMZ_URI
else:
    PGURI = PG_LOCAL_URI

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.logger.info(f"App started using {DBTYPE} database on {datetime.now():%Y-%m-%d %H:%M:%S}")
    print((f"App started using {DBTYPE} database on {datetime.now():%Y-%m-%d %H:%M:%S}"))
    app.config['SECRET_KEY'] = secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = PGURI
    app.config['schema_name'] = os.getenv("schema_name", "secops_db")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['BASE_DIR'] = BASE_DIR  # Store path globally
    app.config['track_modifications'] = True
    app.config['APP_NAME'] = os.getenv("APP_NAME", "Scipher Gaurdz")
    app.config['APP_VERSION'] = os.getenv("APP_VERSION", "2.90.25925")
    app.config['SUPPORT_EMAIL'] = os.getenv("SUPPORT_EMAIL", "scipher.support@vestas.com")
    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    @app.context_processor
    def inject_app_name():
        return {'app_name': app.config.get('APP_NAME', 'APP NAME') }
    @app.context_processor
    def inject_app_version():
        return {'app_version': app.config.get('APP_VERSION', 'APP VERSION') }
    @app.context_processor
    def inject_support_email():
        return {'support_email': app.config.get('SUPPORT_EMAIL', 'scipher.support@vestas.com') }
    # Register blueprints
    from app.main.routes import main
    from app.main.errors import errors
    from app.main.health import health

    app.register_blueprint(main)
    app.register_blueprint(errors)
    app.register_blueprint(health)


    return app

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)
