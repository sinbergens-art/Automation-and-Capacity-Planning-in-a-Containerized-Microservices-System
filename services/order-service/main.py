import os, time, logging
from typing import List, Optional
import httpx, psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] order-service: %(message)s")
logger = logging.getLogger("order-service")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "apppass")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8000")

app = FastAPI(title="Order Service", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


class OrderItem(BaseModel):
    product_id: int
    quantity: int

class OrderRequest(BaseModel):
    username: str
    items: List[OrderItem]

class OrderResponse(BaseModel):
    id: int
    username: str
    total: float
    status: str


def get_db():
    last_err = None
    for attempt in range(5):
        try:
            return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                                    user=DB_USER, password=DB_PASSWORD, connect_timeout=3)
        except Exception as exc:
            last_err = exc
            logger.error("DB connect failed (attempt %s) host=%s: %s",
                         attempt + 1, DB_HOST, exc)
            time.sleep(1)
    raise RuntimeError(f"Could not connect to DB at {DB_HOST}: {last_err}")


SQL_ORDERS = "CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, username VARCHAR(100) NOT NULL, total NUMERIC(12,2) NOT NULL, status VARCHAR(40) NOT NULL DEFAULT 'created', created_at TIMESTAMP DEFAULT NOW())"
SQL_ITEMS  = "CREATE TABLE IF NOT EXISTS order_items (id SERIAL PRIMARY KEY, order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, unit_price NUMERIC(12,2) NOT NULL)"


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_ORDERS)
    cur.execute(SQL_ITEMS)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("order-service: tables ready (db=%s)", DB_HOST)


@app.on_event("startup")
def on_startup():
    try:
        init_db()
    except Exception as exc:
        logger.error("Startup DB init failed: %s", exc)


def row_to_order(row) -> dict:
    return {
        "id":       int(row["id"]),
        "username": row["username"],
        "total":    float(row["total"]),
        "status":   row["status"],
    }


@app.get("/health")
def health():
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                                user=DB_USER, password=DB_PASSWORD, connect_timeout=2)
        conn.close()
        return {"status": "ok", "service": "order-service", "db_host": DB_HOST}
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        raise HTTPException(503, f"DB unreachable: {exc}")


@app.get("/orders", response_model=List[OrderResponse])
def list_orders(username: Optional[str] = None):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if username:
        cur.execute("SELECT * FROM orders WHERE username=%s ORDER BY id DESC", (username,))
    else:
        cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row_to_order(r) for r in rows]


@app.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(req: OrderRequest):
    if not req.items:
        raise HTTPException(400, "Empty order")
    total = 0.0
    priced = []
    with httpx.Client(timeout=5.0) as client:
        for item in req.items:
            try:
                r = client.get(f"{PRODUCT_SERVICE_URL}/products/{item.product_id}")
            except Exception as exc:
                raise HTTPException(502, f"product-service unreachable: {exc}")
            if r.status_code != 200:
                raise HTTPException(400, f"Invalid product {item.product_id}")
            p = r.json()
            line_total = float(p["price"]) * item.quantity
            total += line_total
            priced.append((item.product_id, item.quantity, float(p["price"])))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("INSERT INTO orders (username, total, status) VALUES (%s,%s,'created') RETURNING *",
                (req.username, total))
    order = cur.fetchone()
    for pid, qty, price in priced:
        cur.execute("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s,%s,%s,%s)",
                    (order["id"], pid, qty, price))
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Created order id=%s user=%s total=%s",
                order["id"], req.username, total)
    return row_to_order(order)
