# run.py
import ssl
from app import create_app,db

app = create_app()
with app.app_context():
    db.create_all()

if __name__ == '__main__':

    print("Starting Flask app on port 5001 without SSL for testing...")
    app.run(host='0.0.0.0', port=5001,debug=True)