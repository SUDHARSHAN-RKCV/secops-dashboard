import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

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
    POSTGRES_URI = PG_DMZ_URI
    DBTYPE = "remote"
else:
    POSTGRES_URI = PG_LOCAL_URI
    DBTYPE = "local"
