import os, time, logging
from typing import List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] user-service: %(message)s")
logger = logging.getLogger("user-service")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "apppass")

app = FastAPI(title="User Service", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


class UserProfile(BaseModel):
    id: Optional[int] = None
    username: str
    full_name: str = ""
    bio: str = ""


def get_db():
    last_err = None
    for attempt in range(10):
        try:
            return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                                    user=DB_USER, password=DB_PASSWORD, connect_timeout=3)
        except Exception as exc:
            last_err = exc
            time.sleep(2)
    raise RuntimeError(f"Could not connect to DB: {last_err}")


def init_db():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            full_name VARCHAR(200) DEFAULT '',
            bio TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit(); cur.close(); conn.close()
    logger.info("user-service: profiles table ready")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "user-service"}


@app.get("/users", response_model=List[UserProfile])
def list_users():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM user_profiles ORDER BY id")
    rows = cur.fetchall(); cur.close(); conn.close()
    return [UserProfile(**r) for r in rows]


@app.get("/users/{username}", response_model=UserProfile)
def get_user(username: str):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM user_profiles WHERE username=%s", (username,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "User profile not found")
    return UserProfile(**row)


@app.post("/users", response_model=UserProfile, status_code=201)
def upsert_profile(p: UserProfile):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        INSERT INTO user_profiles (username, full_name, bio)
        VALUES (%s,%s,%s)
        ON CONFLICT (username) DO UPDATE
        SET full_name = EXCLUDED.full_name, bio = EXCLUDED.bio
        RETURNING *
    """, (p.username, p.full_name, p.bio))
    row = cur.fetchone(); conn.commit(); cur.close(); conn.close()
    logger.info("Upserted profile: %s", p.username)
    return UserProfile(**row)
