#seeder.py
# Seeder Script to initialize and seed the databases
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from sqlalchemy import create_engine, text
from app.models import db, User
from flask import Flask

load_dotenv()

REMOTE_DB = os.getenv("POSTGRES_URI")
LOCAL_DB = os.getenv("POSTGRES_local_URI")

SCHEMA_NAME = "secops_db"

def create_app(db_url):
    """Create a temporary Flask app instance bound to a specific DB."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def seed_database(db_url, label):
    print("\n==============================")
    print(f" Seeding {label} DB")
    print("\n==============================")

    if not db_url:
        print(f"❌ {label} DB URL not found. Skipping.")
        return

    app = create_app(db_url)
    engine = create_engine(db_url)

    with app.app_context():
        # Ensure schema exists
        print(f"Ensuring schema `{SCHEMA_NAME}` exists...")
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA_NAME}";'))
            conn.commit()

        # Create tables
        print("Creating tables...")
        db.create_all()

        # Check admin user
        print("Checking for admin user...")
        existing = User.query.filter_by(email="admin@mail.com").first()

        if not existing:
            print("Creating default admin user...")
            admin = User(
                email="admin@mail.com",
                password=generate_password_hash("password123"),
                role="admin",
                is_active=True,
                file_permission="write"
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created.")
        else:
            print("ℹ Admin user already exists. Skipping insert.")

        print(f"✔ Done seeding {label} DB.")


def run_seeder():
    print("Starting Seeder...")

    # Seed Remote DB
    seed_database(REMOTE_DB, "REMOTE")

    # Seed Local DB
    seed_database(LOCAL_DB, "LOCAL")

    print("\n==============================")
    print(" Seeder finished for ALL DBs")
    print("==============================")


if __name__ == "__main__":
    run_seeder()
