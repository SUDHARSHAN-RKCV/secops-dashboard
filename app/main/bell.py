# app/main/bell.py
from flask_login import current_user
from .routes import main

@main.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        #actual logic to be pulled for notifications
        notifications = [
            {"message": "🔔 Security alert on host 10.0.1.14", "link": ""},
            {"message": "📦 New VAPT report uploaded", "link": "/reports/vapt"},
            {"message": "🛠 Maintenance window scheduled", "link": "/maintenance"}
        ]
    else:
        notifications = []
    return {"notifications": notifications}
