# app/main/routes.py
import os
import json
import base64
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
import boto3
import fitz  # PyMuPDF
import mammoth
import markdown
import pandas as pd
import requests
from dateutil import parser as dateparser
from dotenv import load_dotenv
from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect,
    render_template, request, send_file, send_from_directory,
    session, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import cast, create_engine, or_, String
from werkzeug.security import check_password_hash, generate_password_hash
from zoneinfo import ZoneInfo

from app.config import POSTGRES_URI
from app.main.file2data import (
    load_excel_data,
    load_vapt_tracker,
    read_excel_with_flexible_headers,
    safe_format_dates,
    format_dates_dynamic,
    format_utc,
)
from app.models import db, User
from .forms import CreateUserForm

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv()

main = Blueprint("main", __name__, template_folder="templates")

from . import bell  # noqa: E402  (must follow blueprint creation)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Constants & singletons
# ---------------------------------------------------------------------------
engine = create_engine(POSTGRES_URI)

SSC_API_KEY = os.getenv("SSC_API_KEY")
DOMAIN: list[str] = os.getenv("DOMAIN", "").split(",")

IST = timezone(timedelta(hours=5, minutes=30))
IST_STAMP = "%Y-%m-%d IST"

LANDING = "main.home"
UM = "main.UM"

RESET_PASSWORD_FORM_TEMPLATE = "user/reset_password_form.html"

ALLOWED_EXTENSIONS: dict[str, str] = {
    "txt": "text", "log": "text", "md": "text",
    "jpg": "image", "jpeg": "image", "png": "image", "gif": "image",
    "pdf": "pdf",
    "docx": "docx",
    "xlsx": "excel", "xls": "excel",
}

SSC_HEADERS = {
    "Authorization": f"Token {SSC_API_KEY}",
    "Accept": "application/json",
}

SSC_CACHE: dict = {}
SSC_CACHE_TTL = timedelta(hours=24)

# Source-data root (shared across routes)
_UI_SOURCE = Path(__file__).resolve().parents[3] / "source" / "ui"
_DRIVE_SOURCE = Path(__file__).resolve().parents[3] / "source" / "drive"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _admin_required():
    """Abort 403 if the current user is not an admin."""
    if current_user.role.lower() != "admin":
        abort(403)


def _safe_file_path(base: str, relative: str) -> str:
    """
    Resolve *relative* inside *base*, raise 403 on path-traversal attempts.
    Returns the absolute path string.
    """
    safe = os.path.normpath(os.path.join(base, relative.lstrip(os.sep)))
    if not safe.startswith(base):
        abort(403)
    return safe

@main.route("/data/<path:filename>", methods=["GET"])
def data_files(filename):
    return send_from_directory(_UI_SOURCE, filename)



# ---------------------------------------------------------------------------
# Security Scorecard helpers
# ---------------------------------------------------------------------------

def fetch_security_scorecard(domain: str) -> dict:
    """Fetch SSC data for a single domain, with a 24-hour in-memory TTL cache."""
    now = datetime.now(IST)
    cached = SSC_CACHE.get(domain)

    if cached and now - cached["fetched_at"] < SSC_CACHE_TTL:
        return cached["data"]

    try:
        resp = requests.get(
            f"https://api.securityscorecard.io/companies/{domain}",
            headers=SSC_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()

        data = {
            "domain": domain,
            "score": payload.get("score"),
            "grade": payload.get("grade"),
            "grade_url": payload.get("grade_url"),
            "report_url": payload.get("profile", {}).get("url", "#"),
            "last_fetched": now.strftime(IST_STAMP),
            "cached_at": now.strftime(IST_STAMP),
        }
        SSC_CACHE[domain] = {"fetched_at": now, "data": data}
        return data

    except Exception as exc:
        current_app.logger.error("SSC fetch failed for %s: %s", domain, exc)
        if cached:
            return cached["data"]
        return {
            "domain": domain,
            "score": "N/A",
            "grade": None,
            "grade_url": None,
            "report_url": "#",
            "last_fetched": now.strftime(IST_STAMP),
            "error": str(exc),
        }


def fetch_ssc_data(domains: list[str]) -> dict:
    """Fetch SecurityScorecard data for multiple domains."""
    return {d: fetch_security_scorecard(d) for d in domains}


# ---------------------------------------------------------------------------
# Home route
# ---------------------------------------------------------------------------

@main.route("/", methods=["GET"])
def home():
    base_path = _UI_SOURCE

    # --- SSC ---
    try:
        ssc_all_data = fetch_ssc_data(DOMAIN)
    except Exception:
        current_app.logger.exception("SSC bulk fetch failed")
        ssc_all_data = {}

    ssc_last_fetched = None
    if ssc_all_data:
        ssc_last_fetched = next(iter(ssc_all_data.values())).get("last_fetched")

    # --- VAPT images ---
    vapt_img_dir = base_path / "vapt-img"
    current_year = str(datetime.now().year)
    vapt_images, selected_vapt, vapt_last_modified = [], None, None

    if vapt_img_dir.exists():
        vapt_images = sorted(
            f.name for f in vapt_img_dir.iterdir()
            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg"}
        )
        # Prefer current-year image; fall back to newest
        selected_vapt = next(
            (n for n in vapt_images if current_year in n), None
        ) or (vapt_images[-1] if vapt_images else None)

        if selected_vapt:
            vapt_last_modified = format_utc(
                os.path.getmtime(vapt_img_dir / selected_vapt)
            )

    # --- EC2 OS Patch ---
    ospatch_path = base_path / "ec2-patch.xlsx"
    raw_patch = pd.read_excel(ospatch_path, sheet_name=None)
    os_patch_sheets = {
        sheet: format_dates_dynamic(df).to_dict(orient="records")
        for sheet, df in raw_patch.items()
    }
    ospatch_last_modified = format_utc(os.path.getmtime(ospatch_path))

    # --- Projects ---
    project_path = base_path / "projects.xlsx"
    project_headers, project_records = load_excel_data(project_path)
    project_last_modified = format_utc(os.path.getmtime(project_path))

    # --- Accomplished Activities (all sheets) ---
    activity_path = base_path / "Accomplished_Activities.xlsx"
    raw_activity = pd.read_excel(activity_path, sheet_name=None)
    activity_sheets = {
        sheet: df.where(df.notna(), "").to_dict(orient="records")
        for sheet, df in raw_activity.items()
    }
    activity_last_modified = format_utc(os.path.getmtime(activity_path))

    return render_template(
        "home.html",
        project_headers=project_headers,
        project_records=project_records,
        project_last_modified=project_last_modified,
        activity_sheets=activity_sheets,
        activity_last_modified=activity_last_modified,
        os_patch_sheets=os_patch_sheets,
        ospatch_last_modified=ospatch_last_modified,
        vapt_last_modified=vapt_last_modified,
        vapt_images=vapt_images,
        selected_vapt=selected_vapt,
        ssc_all_data=ssc_all_data,
        ssc_last_fetched=ssc_last_fetched,
    )


# ---------------------------------------------------------------------------
# Reports / File viewer
# ---------------------------------------------------------------------------


@main.route("/dashboard", methods=["GET"])
def dashboard():
    try:
        dashboard_urls = json.loads(os.getenv("DASHBOARD_URLS", "[]"))
    except json.JSONDecodeError:
        dashboard_urls = []
    return render_template(
        "dashboard.html",
        dashboards=dashboard_urls,
        active_page="dashboard",
        current_user=current_user,
    )

@main.route("/reports/", methods=["GET"])
@main.route("/reports/<path:path>", methods=["GET"])
@login_required
def reports():
    try:
        reports_urls = json.loads(os.getenv("SOC_REPORTS_URLS", "[]"))
    except json.JSONDecodeError:
        reports_urls = []
    return render_template(
        "reports.html",
        Reports=reports_urls,
        active_page="reports",
        current_user=current_user,
    )

# ---------------------------------------------------------------------------
# Misc UI routes
# ---------------------------------------------------------------------------

@main.route("/projects", methods=["GET"])
@login_required
def projects():
    return render_template("projects.html", active_page="projects", current_user=current_user)


@main.route("/tools", methods=["GET"])
def tools():
    return render_template("tools.html", active_page="tools", current_user=current_user)

@main.route("/changelog", methods=["GET"])
@login_required
def changelog():
    changelog_path = Path(current_app.root_path) / ".." / "changelog.md"
    try:
        md_content = changelog_path.read_text(encoding="utf-8")
        html_content = markdown.markdown(md_content, extensions=["fenced_code", "tables"])
    except Exception as exc:
        current_app.logger.error("Failed to load changelog: %s", exc)
        html_content = "<p><strong>Error loading changelog.</strong></p>"
    return render_template("changelog.html", changelog_html=html_content, active_page="changelog")


@main.route("/reports/vapt", methods=["GET"])
def vapt():
    return redirect(url_for(LANDING))


@main.route("/maintenance", methods=["GET"])
def maintenance():
    return redirect(url_for(LANDING))


@main.route("/health", methods=["GET"])
def health_ui():
    return render_template("health.html")


# ---------------------------------------------------------------------------
# Security Scorecard report routes
# ---------------------------------------------------------------------------

@main.route("/full-reports/<domain>", methods=["GET"])
@login_required
def full_reports(domain):
    resp = requests.get(
        f"https://api.securityscorecard.io/companies/{domain}/factors/",
        headers=SSC_HEADERS,
    )
    if resp.status_code == 200:
        data = resp.json()
        return render_template("full_report.html", domain=domain, entries=data.get("entries", []))
    current_app.logger.error("SSC full_report error %s for %s", resp.status_code, domain)
    abort(502)


@main.route("/full-report/<domain>", methods=["GET"])
@login_required
def full_report(domain):
    try:
        resp = requests.get(
            f"https://api.securityscorecard.io/companies/{domain}/",
            headers=SSC_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        factors = resp.json().get("factors", [])
        current_app.logger.info("SSC factors for %s: %s", domain, factors)

        entries = [
            {"name": f.get("name", "Unknown"), "score": f.get("score", "N/A"),
             "grade_url": f.get("grade_url"), "issue_summary": f.get("issue_summary", []),
             **f}
            for f in factors
        ]
        return render_template("full_report.html", domain=domain, entries=entries)

    except Exception as exc:
        current_app.logger.error("Full report fetch failed for %s: %s", domain, exc)
        abort(502)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return "", 204
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for(LANDING))
        flash("Invalid email or password.", "danger")
    return render_template("user/login.html")


@main.route("/logout", methods=["GET"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for(LANDING))


@main.route("/settings", methods=["GET", "POST"])
@login_required
def user_settings():
    if request.method == "POST":
        current_user.theme = request.form.get("theme", "system")
        db.session.commit()
        flash("Settings updated.", "success")
        return redirect(url_for("main.user_settings"))
    return render_template("user/settings.html", current_user=current_user)


# ---------------------------------------------------------------------------
# Admin — User Management
# ---------------------------------------------------------------------------

@main.route("/UM", methods=["GET"])
@login_required
def user_management():
    _admin_required()

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str)
    role = request.args.get("role", "", type=str)
    per_page = 50

    query = User.query
    if search:
        query = query.filter(
            or_(
                User.email.ilike(f"%{search}%"),
                User.role.ilike(f"%{search}%"),
                cast(User.user_id, String).ilike(f"%{search}%"),
            )
        )
    if role:
        query = query.filter(User.role == role)

    users = query.order_by(User.user_created_on.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template("user/UM.html", users=users.items, pagination=users, active_page="UM")


@main.route("/create", methods=["POST"])
@login_required
def create_user_post():
    _admin_required()
    new_user = User(
        email=request.form["email"],
        password=generate_password_hash(request.form["password"]),
        role=request.form["role"].upper(),
        is_active=True,
        file_permission=request.form.get("file_permission", "none"),
    )
    db.session.add(new_user)
    db.session.commit()
    flash("User created successfully", "success")
    return redirect(url_for("main.user_management"))


@main.route("/<uuid:user_id>/edit", methods=["POST"])
@login_required
def edit_user(user_id: UUID):
    _admin_required()
    user = User.query.get_or_404(user_id)
    user.role = request.form["role"].upper()
    user.is_active = "is_active" in request.form
    user.file_permission = request.form.get("file_permission", "none")
    db.session.commit()
    flash("User updated successfully", "success")
    return redirect(url_for("main.user_management"))

@main.route("/reset-password-form", methods=["GET", "POST"])
def reset_password_form():
    return render_template(RESET_PASSWORD_FORM_TEMPLATE, email="")


@main.route("/reset-password", methods=["GET", "POST"])
@main.route("/forgot-password", methods=["GET", "POST"])
def reset_password_form_handler():
    email = request.form.get("email")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not email:
        flash("Email is required.", "danger")
        return redirect(url_for("main.reset_password_form"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User does not exist.", "danger")
        return redirect(url_for("main.reset_password_form"))

    if not new_password or len(new_password) < 8:
        flash("Password must be at least 8 characters long.", "danger")
        return render_template(RESET_PASSWORD_FORM_TEMPLATE, email=email)

    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return render_template(RESET_PASSWORD_FORM_TEMPLATE, email=email)

    user.password = generate_password_hash(new_password)
    db.session.commit()
    flash("Password has been reset successfully. Please log in.", "success")
    return redirect(url_for("main.login"))

@main.route("/<uuid:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id: UUID):
    _admin_required()
    user = User.query.get_or_404(user_id)
    
    if user.role.upper() == "ADMIN":
        flash("Admin users cannot be deleted.", "danger")
        return redirect(url_for("main.user_management"))
    
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully", "success")
    return redirect(url_for("main.user_management"))

@main.route("/<uuid:user_id>/toggle", methods=["POST"])
@login_required
def toggle_user_status(user_id: UUID):
    _admin_required()
    user = User.query.get_or_404(user_id)
    if user.role.upper() == "ADMIN":
        flash("Admin users cannot be Altered.", "danger")
        return redirect(url_for("main.user_management"))
    user.is_active = not user.is_active
    db.session.commit()
    flash("User status toggled", "info")
    return redirect(url_for("main.user_management"))


@main.route("/<uuid:user_id>/reset_password", methods=["POST"])
@login_required
def admin_reset_password(user_id: UUID):
    _admin_required()
    user = User.query.get_or_404(user_id)
    new_password = request.form.get("new_password")
    if not new_password:
        flash("Password cannot be empty.", "danger")
        return redirect(url_for("main.user_management"))
    user.password = generate_password_hash(new_password)
    db.session.commit()
    flash("Password has been reset successfully.", "warning")
    return redirect(url_for("main.user_management"))