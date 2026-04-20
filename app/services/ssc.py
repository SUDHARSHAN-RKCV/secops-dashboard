from datetime import datetime, timedelta, timezone
from sqlalchemy import text
import requests
from flask import current_app
from app.models import db
from app.main.routes import Headers, utcstamp,iststamp

SSC_TTL = timedelta(hours=24)

def fetch_security_scorecard(domain: str) -> dict:
    
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST)
    iststamp = "%Y-%m-%d %H:%M IST"
    # 1. Try DB cache
    row = db.session.execute(
        text("""
            SELECT payload, fetched_at
            FROM ssc_cache
            WHERE domain = :domain
        """),
        {"domain": domain}
    ).fetchone()

    if row:
        payload, fetched_at = row
        if now - fetched_at < SSC_TTL:
            return payload

    # 2. Fetch from SSC API
    url = f"https://api.securityscorecard.io/companies/{domain}"
    try:
        resp = requests.get(url, headers=Headers, timeout=10)
        resp.raise_for_status()
        api_data = resp.json()

        data = {
            "domain": domain,
            "score": api_data.get("score"),
            "grade": api_data.get("grade"),
            "grade_url": api_data.get("grade_url"),
            "report_url": api_data.get("profile", {}).get("url", "#"),
            "last_fetched": now.strftime(iststamp),
        }

        # 3. Upsert cache
        db.session.execute(
            text("""
                INSERT INTO ssc_cache (domain, payload, fetched_at)
                VALUES (:domain, :payload, :fetched_at)
                ON CONFLICT (domain)
                DO UPDATE SET
                    payload = EXCLUDED.payload,
                    fetched_at = EXCLUDED.fetched_at
            """),
            {
                "domain": domain,
                "payload": data,
                "fetched_at": now,
            }
        )
        db.session.commit()

        return data

    except Exception as e:
        current_app.logger.error(f"SSC fetch failed for {domain}: {e}")

        # 4. Fail closed but usable
        if row:
            return row.payload

        return {
            "domain": domain,
            "score": "N/A",
            "grade": None,
            "report_url": "#",
            "error": "SSC unavailable",
        }
