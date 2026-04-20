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

import uuid
import random
from datetime import datetime
from zoneinfo import ZoneInfo

def current_ist_time():
    return datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None, microsecond=0)


def seed_fake_users(count=500_000, batch_size=20_000):
    print(f"🚀 Seeding {count} fake users...")

    roles = ["admin", "user", "viewer", "editor"]
    total_inserted = 0

    while total_inserted < count:
        batch = []

        for i in range(batch_size):
            index = total_inserted + i

            batch.append({
                "user_id": uuid.uuid4(),
                "email": f"user{index}@loadtest.com",
                "password": "test",  # no hashing
                "role": random.choice(roles),
                "is_active": True,
                "file_permission": "read",
                "user_created_on": current_ist_time()
            })

        db.session.bulk_insert_mappings(User, batch)
        db.session.commit()

        total_inserted += batch_size
        print(f"Inserted {total_inserted}/{count}")

    print("✅ Fake user seeding complete.")

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


#if __name__ == "__main__":
    #run_seeder()

if __name__ == "__main__":
    app = create_app(LOCAL_DB)  # or REMOTE_DB

    with app.app_context():
        seed_fake_users(500_000)