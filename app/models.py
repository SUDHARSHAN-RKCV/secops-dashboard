# models.py

import uuid
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.dialects.postgresql import UUID
import os
from dotenv import load_dotenv
load_dotenv()

schema_name=os.getenv("schema_name", "secops_db")

def current_ist_time():
    return datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None, microsecond=0)

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = {'schema': schema_name}  # Change schema name if needed

    user_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    email = db.Column(db.String, nullable=False, unique=True, index=True)
    password = db.Column(db.String, nullable=False)
    role = db.Column(db.String, nullable=True, index=True)
    user_created_on = db.Column(db.DateTime, default=current_ist_time, nullable=False)
    last_modified_on = db.Column(db.DateTime, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    theme = db.Column(db.String(10), default='system')
    file_permission = db.Column(db.String(10), default='none') 

    def get_id(self):
        return str(self.user_id)