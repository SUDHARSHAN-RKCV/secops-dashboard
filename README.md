# secops-dashboard

# 🛡️ Scipher Guardz — SecOps Dashboard

> A Flask-based internal Security Operations dashboard providing a single-pane-of-glass view of the organisation's security posture.

![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey?logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Azure-336791?logo=postgresql&logoColor=white)
![Version](https://img.shields.io/badge/Version-2.9.20226-green)
![License](https://img.shields.io/badge/License-Internal%20Use-red)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
  - [Database Setup](#database-setup)
  - [Running the App](#running-the-app)
- [Production Deployment](#production-deployment)
- [User Roles & Permissions](#user-roles--permissions)
- [Data Files](#data-files)
- [External Integrations](#external-integrations)
- [API Endpoints](#api-endpoints)
- [Changelog](#changelog)

---

## Overview

**Scipher Guardz** is an internal SecOps web application built for the Vestas / Scipher security team. It aggregates data from multiple security tools and sources into a unified dashboard, enabling security operators to monitor posture, track vulnerabilities, manage projects, and browse reports — all in one place.

---

## Features

- 🔐 **Role-based authentication** — Admin and User roles with session-based login
- 📊 **SecurityScorecard integration** — Live security grades for configured domains with 24h caching
- 📋 **Project & Activity tracking** — Excel-driven project cards and accomplished activities
- 🩹 **EC2 OS Patch status** — Multi-sheet patch tracker rendered from Excel
- 🔍 **VAPT report viewer** — Image-based VAPT scan results with year-aware selection
- 📁 **File Manager** — Permission-gated file browser with preview (PDF, DOCX, Excel, images, text)
- 📺 **Embedded Dashboards** — Configurable iframes for Datadog WAF, Dynatrace, Wazuh, and more
- 🛠️ **Tools Hub** — Quick-launch links for Snyk, SonarQube, Jenkins, and other SecOps tools
- 👥 **User Management** — Admin panel to create, edit, activate/deactivate, and reset user passwords
- 📜 **Changelog page** — Rendered from `changelog.md` automatically
- ❤️ **Health check endpoint** — `/health_api` for liveness monitoring
- 🌙 **Theme support** — Light, dark, and system theme preference per user

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| Web Framework | Flask (Blueprints) |
| ORM | Flask-SQLAlchemy / SQLAlchemy |
| Database | PostgreSQL (Azure primary + local fallback) |
| Auth | Flask-Login + Werkzeug (bcrypt) |
| Forms | Flask-WTF / WTForms |
| Templates | Jinja2 |
| Data Processing | pandas, openpyxl |
| PDF Preview | PyMuPDF (fitz) |
| DOCX Preview | mammoth |
| Markdown Rendering | markdown (Python) |
| HTTP Client | requests |
| Real-time | Flask-SocketIO (eventlet) |
| Task Scheduling | APScheduler |
| Caching | Flask-Caching |
| Rate Limiting | Flask-Limiter |
| Migrations | Flask-Migrate (Alembic) |
| WSGI Server | Gunicorn (production) |
| Config | python-dotenv |

---

## Project Structure

```
secops-dashboard/
├── app/
│   ├── __init__.py              # App factory (create_app)
│   ├── config.py                # DB connectivity + automatic failover logic
│   ├── models.py                # SQLAlchemy User model
│   ├── static/
│   │   ├── css/style.css        # Application styles
│   │   ├── js/scripts.js        # Frontend scripts
│   │   ├── logos/               # Tool logos (Datadog, Wazuh, Snyk, etc.)
│   │   └── sources/             # ⚠️  UI data files (Excel, VAPT images)
│   └── main/
│       ├── routes.py            # All URL routes
│       ├── bell.py              # Notification context processor
│       ├── errors.py            # HTTP error handlers
│       ├── file2data.py         # Excel ingestion helpers
│       ├── forms.py             # WTForms form classes
│       ├── health.py            # /health_api blueprint
│       └── templates/
│           ├── base.html        # Master layout
│           ├── home.html        # Main dashboard / homepage
│           ├── dashboard.html   # Embedded tool dashboards
│           ├── reports.html     # File browser
│           ├── full_report.html # SSC detailed factor report
│           ├── tools.html       # Tools listing
│           ├── changelog.html   # Changelog renderer
│           ├── health.html      # Health status page
│           ├── errors/          # 400, 401, 403, 404, 405, 413, 429, 500
│           ├── macros/          # Reusable Jinja2 macros
│           └── user/            # Login, User Management, Settings templates
├── run.py                       # Entry point — HTTPS on port 443
├── wsgi.py                      # WSGI entry point for Gunicorn
├── gunicorn_config.py           # Gunicorn configuration
├── seeder.py                    # DB schema initialiser + default admin seeder
├── requirements.txt             # Python dependencies
├── .env                         # ⚠️  Environment variables (never commit)
├── changelog.md                 # Version history
└── prod/
    └── secops-dash.service      # systemd service unit file
```

---

## Getting Started

### Prerequisites

- Python 3.12 or 3.13
- PostgreSQL (Azure-hosted or local)
- pip / virtualenv

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd secops-dashboard

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
# .\venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and fill in all values before running the app.

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `APP_NAME` | Application display name |
| `APP_VERSION` | Version string shown in the footer |
| `MAINTENANCE_MODE` | Set `true` to enable maintenance redirect |
| `MAINTENANCE_WINDOW` | ISO 8601 interval string for the maintenance window |
| `SUPPORT_EMAIL` | Support email shown in error pages |
| `session_secret_key` | **Strong random string** — used to sign Flask sessions |
| `POSTGRES_URI` | Primary PostgreSQL connection string (Azure) |
| `POSTGRES_local_URI` | Fallback local PostgreSQL connection string |
| `schema_name` | PostgreSQL schema name (default: `secops_db`) |
| `DASHBOARD_URLS` | JSON array of `{"title": "...", "url": "..."}` for embedded dashboards |
| `DOMAIN` | Comma-separated domains for SecurityScorecard lookups |
| `SSC_API_KEY` | SecurityScorecard API token |

> ⚠️ **Never commit `.env` to source control.** Add it to `.gitignore`.

### Database Setup

Run the seeder script once on a fresh install to create the schema, tables, and a default admin account:

```bash
python seeder.py
```

This will:
- Create the `secops_db` schema (if it doesn't exist)
- Create the `users` table
- Insert a default admin user

> 🔑 **Default credentials:** `admin@mail.com` / `password123`
> **Change these immediately** after first login via Admin → User Management.

### Running the App

**Development (HTTP, port 5001):**

Uncomment the non-SSL lines in `run.py`:

```bash
python run.py
```

**Production (HTTPS, port 443):**

Requires SSL certificates at `/opt/ssl-certs/`:

```bash
# Grant port 443 binding capability to the venv Python binary
sudo setcap 'cap_net_bind_service=+ep' /path/to/venv/bin/python3

# Run directly
python run.py
```

**With Gunicorn:**

```bash
gunicorn --config gunicorn_config.py run:app
```

---

## Production Deployment

The app runs as a **systemd service** on a Linux host.

### Setup

```bash
# 1. Copy project to server
cp -r secops-dashboard/ /opt/secops-dash/

# 2. Create startup script at /opt/secops-dash/SecopsDashboard.sh
chmod +x /opt/secops-dash/SecopsDashboard.sh

# 3. Grant port 443 capability
sudo setcap 'cap_net_bind_service=+ep' /opt/secops-dash/venv/bin/python3

# 4. Install and enable the systemd service
sudo cp prod/secops-dash.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now secops-dash
```

### Service Management

```bash
sudo systemctl status  secops-dash     # Check status
sudo systemctl restart secops-dash     # Restart
sudo systemctl stop    secops-dash     # Stop

# View today's logs
tail -f /var/log/secops-dash/$(date +"%d%m%y")-secops-dash.log

# Confirm port 443 is bound
sudo lsof -i:443
```

### SSL Certificates

Place certificates at:

```
/opt/ssl-certs/fullchain.crt
/opt/ssl-certs/scipher.secops.com.key
/opt/ssl-certs/chain.crt
```

---

## User Roles & Permissions

### Roles

| Role | Description |
|---|---|
| `ADMIN` | Full access including User Management (create / edit / delete / reset passwords) |
| `USER` | Standard authenticated access to dashboard, reports, tools, and file manager |

### File Permissions (`file_permission` column)

| Value | Capabilities |
|---|---|
| `none` | No file manager access |
| `basic` | Download files only |
| `view` | List, preview, download, and upload files |
| `write` | Full access — list, preview, download, upload, edit, and delete |

---

## Data Files

The homepage reads data from flat files. These must be present on the server:

| File | Path | Purpose |
|---|---|---|
| `ec2-patch.xlsx` | `app/static/sources/` | EC2 OS patch status (multi-sheet) |
| `projects.xlsx` | `app/static/sources/` | Active security projects |
| `Accomplished_Activities.xlsx` | `app/static/sources/` | Completed activity log (multi-sheet) |
| `vapt-img/*.png` | `app/static/sources/vapt-img/` | VAPT scan result images |
| Report files | `source/drive/` (3 levels above `app/`) | Files served by the `/reports` file browser |

> The app selects the VAPT image whose filename contains the current year, falling back to the most recent file if none matches.

---

## External Integrations

### SecurityScorecard API

Fetches security grade data for all domains defined in `DOMAIN`. Results are cached in-memory for **24 hours**.

- **Endpoint:** `https://api.securityscorecard.io/companies/{domain}`
- **Auth:** `Authorization: Token {SSC_API_KEY}`
- **Fallback:** Returns cached data on failure; shows `N/A` if no cache exists

### Embedded Dashboards

Configure iframes via the `DASHBOARD_URLS` env var:

```json
[
  {"title": "WAF Dashboard", "url": "https://p.datadoghq.eu/sb/..."}
]
```

---

## API Endpoints

| Method | Route | Auth | Description |
|---|---|---|---|
| `GET` | `/` | Public | Homepage — SSC scores, VAPT, patch data, projects |
| `GET/POST` | `/login` | Public | Login |
| `GET` | `/logout` | Required | Logout |
| `GET` | `/dashboard` | Public | Embedded tool dashboards |
| `GET` | `/tools` | Public | SecOps tools hub |
| `GET` | `/reports/[path]` | Required | File browser |
| `GET` | `/full-report/<domain>` | Required | SSC factor report |
| `GET` | `/changelog` | Required | Changelog viewer |
| `GET` | `/health_api` | Public | JSON liveness check |
| `GET` | `/api/tree` | Required | Directory tree JSON |
| `GET` | `/api/preview` | Public | File preview JSON |
| `GET` | `/file-manager/list` | Required | Directory listing |
| `POST` | `/file-manager/upload/local` | Required | Upload file |
| `POST` | `/file-manager/edit/local/<path>` | Required | Edit file |
| `DELETE` | `/file-manager/delete/local/<path>` | Required | Delete file |
| `GET` | `/file-manager/download/local/<path>` | Required | Download file |
| `GET` | `/UM` | Admin | User management |
| `POST` | `/create` | Admin | Create user |
| `POST` | `/<uuid>/edit` | Admin | Edit user |
| `POST` | `/<uuid>/delete` | Admin | Delete user |
| `POST` | `/<uuid>/reset_password` | Admin | Reset user password |
| `GET/POST` | `/reset-password` | Public | Self-service password reset |
| `GET/POST` | `/settings` | Required | User theme settings |

---

## Changelog

See [changelog.md](changelog.md) for the full version history.

| Version | Highlights |
|---|---|
| **v2.9.20226** | WAF migrated to Datadog, PDF viewer, monitoring tool tabs |
| v2.8.25925 | Monitoring tabs, PDF viewer, navigation cleanup |
| v2.0.28725 | HTTPS/SSL, password reset, notifications, WAF graphs |
| v1.5.25525 | Admin UM modals, improved UI, date parsing fixes |
| v1.0.25425 | Initial release — SSC integration, PostgreSQL charts, role-based login |

---

<div align="center">
  <sub>Built for Vestas / Scipher Security Operations · Internal Use Only</sub>
</div>
