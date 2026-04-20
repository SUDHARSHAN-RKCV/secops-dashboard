#app/main/health.py
from flask import Blueprint, jsonify, render_template
from sqlalchemy import text
from app.models import db  # adjust import

health = Blueprint("health", __name__)

@health.route("/health_api", methods=["GET"])
def health_check():
    status = {
        "UI": "ok",
        "Database": "unknown",
    }

    http_status = 200

    # Check database
    try:
        db.session.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as e:
        status["database"] = "error"
        status["database_error"] = str(e)
        http_status = 503

    return jsonify(status), http_status
