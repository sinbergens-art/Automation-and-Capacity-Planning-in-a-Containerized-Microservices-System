import os, time, logging
from typing import List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] chat-service: %(message)s")
logger = logging.getLogger("chat-service")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "apppass")

app = FastAPI(title="Chat Service", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


class Message(BaseModel):
    id: Optional[int] = None
    sender: str
    receiver: str
    body: str
    created_at: Optional[str] = None

class SendRequest(BaseModel):
    sender: str
    receiver: str
    body: str


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
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            sender VARCHAR(100) NOT NULL,
            receiver VARCHAR(100) NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_msg_pair ON messages (sender, receiver, created_at DESC);")
    conn.commit(); cur.close(); conn.close()
    logger.info("chat-service: messages table ready")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "chat-service"}


@app.post("/chat/send", response_model=Message, status_code=201)
def send(req: SendRequest):
    if not req.body.strip():
        raise HTTPException(400, "Empty message")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("INSERT INTO messages (sender, receiver, body) VALUES (%s,%s,%s) RETURNING *",
                (req.sender, req.receiver, req.body))
    row = cur.fetchone(); conn.commit(); cur.close(); conn.close()
    logger.info("msg %s -> %s", req.sender, req.receiver)
    row["created_at"] = row["created_at"].isoformat()
    return Message(**row)


@app.get("/chat/conversation", response_model=List[Message])
def conversation(user_a: str, user_b: str, limit: int = 100):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM messages
        WHERE (sender=%s AND receiver=%s) OR (sender=%s AND receiver=%s)
        ORDER BY created_at ASC LIMIT %s
    """, (user_a, user_b, user_b, user_a, limit))
    rows = cur.fetchall(); cur.close(); conn.close()
    out = []
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
        out.append(Message(**r))
    return out


@app.get("/chat/inbox/{username}", response_model=List[Message])
def inbox(username: str, limit: int = 50):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM messages WHERE receiver=%s ORDER BY created_at DESC LIMIT %s",
                (username, limit))
    rows = cur.fetchall(); cur.close(); conn.close()
    out = []
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
        out.append(Message(**r))
    return out
