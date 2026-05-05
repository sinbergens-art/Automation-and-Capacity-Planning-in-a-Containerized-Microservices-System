import os
import time
import logging
from typing import List, Optional
 
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
 
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] product-service: %(message)s")
logger = logging.getLogger("product-service")
 
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "apppass")
 
app = FastAPI(title="Product Service", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
 
 
class Product(BaseModel):
    id: Optional[int] = None
    name: str
    description: str = ""
    price: float
    stock: int = 0
 
 
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
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            price NUMERIC(12,2) NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO products (name, description, price, stock) VALUES (%s,%s,%s,%s)",
            [
                ("Laptop Pro 14",  "M-class laptop, 16GB RAM",     1499.00, 25),
                ("Wireless Mouse", "Ergonomic 2.4GHz mouse",         29.90, 200),
                ("Mechanical Keyboard", "RGB, hot-swappable",       129.00, 75),
                ("USB-C Hub 7-in-1", "HDMI/SD/USB3 multiport",       49.50, 120),
                ("4K Monitor 27\"", "IPS, 60Hz, USB-C delivery",    349.99, 40),
            ],
        )
    conn.commit(); cur.close(); conn.close()
    logger.info("product-service: products table ready")
 
 
@app.on_event("startup")
def on_startup():
    init_db()
 
 
@app.get("/health")
def health():
    return {"status": "ok", "service": "product-service"}
 
 
@app.get("/products", response_model=List[Product])
def list_products():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM products ORDER BY id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [Product(**r) for r in rows]
 
 
@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM products WHERE id=%s", (product_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "Product not found")
    return Product(**row)
 
 
@app.post("/products", response_model=Product, status_code=201)
def create_product(p: Product):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "INSERT INTO products (name, description, price, stock) VALUES (%s,%s,%s,%s) RETURNING *",
        (p.name, p.description, p.price, p.stock),
    )
    row = cur.fetchone(); conn.commit()
    cur.close(); conn.close()
    logger.info("Created product id=%s", row["id"])
    return Product(**row)
 