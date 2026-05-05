import os, time, logging
from datetime import datetime, timedelta
import jwt, bcrypt, psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] auth-service: %(message)s")
logger = logging.getLogger("auth-service")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "apppass")

JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

app = FastAPI(title="Auth Service", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def hash_password(plain: str) -> str:
    plain_bytes = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(plain_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    plain_bytes = plain.encode("utf-8")[:72]
    return bcrypt.checkpw(plain_bytes, hashed.encode("utf-8"))


def get_db():
    last_err = None
    for attempt in range(10):
        try:
            return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                                    user=DB_USER, password=DB_PASSWORD, connect_timeout=3)
        except Exception as exc:
            last_err = exc
            logger.warning("DB connect failed (%s): %s", attempt + 1, exc)
            time.sleep(2)
    raise RuntimeError(f"Could not connect to DB: {last_err}")


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("auth-service: users table ready")


@app.on_event("startup")
def on_startup():
    init_db()


def create_token(username: str) -> str:
    payload = {"sub": username,
               "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth-service"}


@app.post("/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id FROM users WHERE username=%s OR email=%s",
                (req.username, req.email))
    if cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="User already exists")
    pw_hash = hash_password(req.password)
    cur.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (req.username, req.email, pw_hash))
    conn.commit(); cur.close(); conn.close()
    logger.info("Registered user: %s", req.username)
    return TokenResponse(access_token=create_token(req.username))


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE username=%s", (req.username,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    logger.info("Login OK: %s", req.username)
    return TokenResponse(access_token=create_token(req.username))


@app.get("/auth/me")
def me(username: str = Depends(verify_token)):
    return {"username": username}
