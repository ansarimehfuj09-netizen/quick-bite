import os, json, time, hmac, hashlib
from datetime import datetime
from typing import List
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------- SETTINGS (yahan badal sakte ho) ----------
RESTAURANT = os.getenv("RESTAURANT_NAME", "Quick Bite")
DELIVERY_FEE = int(os.getenv("DELIVERY_FEE", "30"))
FREE_DELIVERY_ABOVE = int(os.getenv("FREE_DELIVERY_ABOVE", "299"))
MIN_ORDER = int(os.getenv("MIN_ORDER", "99"))
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24).hex())

MENU = [
 {"id":1,"n":"Veg Steamed Momos (8 pcs)","c":"Momos","p":80,"e":"🥟","v":1,"d":"Soft steamed dumplings with spicy chutney"},
 {"id":2,"n":"Paneer Steamed Momos (8 pcs)","c":"Momos","p":100,"e":"🥟","v":1,"d":"Rich paneer filling, aromatic spices"},
 {"id":3,"n":"Chicken Steamed Momos (8 pcs)","c":"Momos","p":120,"e":"🥟","v":0,"d":"Juicy minced chicken momos"},
 {"id":4,"n":"Veg Fried Momos (8 pcs)","c":"Momos","p":90,"e":"🥟","v":1,"d":"Golden fried, crispy outside"},
 {"id":5,"n":"Veg Kurkure Momos (8 pcs)","c":"Momos","p":130,"e":"💥","v":1,"d":"Extra crunchy coated momos"},
 {"id":6,"n":"Paneer Kurkure Momos (8 pcs)","c":"Momos","p":150,"e":"💥","v":1,"d":"Crispy paneer momos with seasoning"},
 {"id":7,"n":"Tandoori Gravy Momos (8 pcs)","c":"Momos","p":160,"e":"🔥","v":1,"d":"Tossed in creamy tandoori gravy"},
 {"id":8,"n":"Veg Hakka Chowmein","c":"Chowmein","p":80,"e":"🍜","v":1,"d":"Classic wok-tossed street style"},
 {"id":9,"n":"Paneer Chowmein","c":"Chowmein","p":110,"e":"🍜","v":1,"d":"Loaded with paneer cubes"},
 {"id":10,"n":"Egg Chowmein","c":"Chowmein","p":100,"e":"🍳","v":0,"d":"Noodles tossed with scrambled egg"},
 {"id":11,"n":"Chicken Chowmein","c":"Chowmein","p":130,"e":"🍜","v":0,"d":"Spicy chicken noodles"},
 {"id":12,"n":"Singapuri Chowmein","c":"Chowmein","p":120,"e":"🌶️","v":1,"d":"Hot and spicy special sauces"},
 {"id":13,"n":"Classic Salted Fries","c":"Fries & Potato","p":70,"e":"🍟","v":1,"d":"Golden crispy potato fries"},
 {"id":14,"n":"Peri Peri Fries","c":"Fries & Potato","p":90,"e":"🍟","v":1,"d":"Fiery peri peri seasoning"},
 {"id":15,"n":"Cheese Loaded Fries","c":"Fries & Potato","p":120,"e":"🧀","v":1,"d":"Hot fries with melted cheese sauce"},
 {"id":16,"n":"Crispy Chilli Potato","c":"Fries & Potato","p":90,"e":"🥔","v":1,"d":"Sweet-spicy garlic glaze"},
 {"id":17,"n":"Honey Chilli Potato","c":"Fries & Potato","p":110,"e":"🍯","v":1,"d":"Honey glaze with sesame seeds"},
 {"id":18,"n":"Cold Coffee","c":"Drinks","p":80,"e":"🥤","v":1,"d":"Thick creamy chilled coffee"},
 {"id":19,"n":"Cold Drink (500ml)","c":"Drinks","p":40,"e":"🥤","v":1,"d":"Chilled soft drink"},
]
STATUSES = ["Received", "Preparing", "On Way", "Delivered", "Cancelled"]

# ---------- DATABASE ----------
url = os.getenv("DATABASE_URL", "sqlite:///quick_bite.db")
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)
engine = create_engine(url, pool_pre_ping=True,
                       connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    name = Column(String(80)); phone = Column(String(15)); address = Column(Text)
    items = Column(Text); total = Column(Float); pay = Column(String(30))
    status = Column(String(20), default="Received")
    created = Column(DateTime, default=datetime.utcnow)
Base.metadata.create_all(engine)

# ---------- OWNER LOGIN ----------
fails = {}
def make_token():
    exp = str(int(time.time()) + 12 * 3600)
    return exp + "." + hmac.new(SECRET_KEY.encode(), exp.encode(), hashlib.sha256).hexdigest()
def check_token(tok):
    try:
        exp, sig = (tok or "").split(".")
        good = hmac.new(SECRET_KEY.encode(), exp.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good) or int(exp) < time.time():
            raise ValueError
    except Exception:
        raise HTTPException(401, "Login required")

app = FastAPI(title=RESTAURANT)

class Line(BaseModel):
    id: int
    qty: int
class NewOrder(BaseModel):
    name: str; phone: str; address: str; pay: str; items: List[Line]
class Login(BaseModel):
    password: str
class SetStatus(BaseModel):
    id: int; status: str

@app.get("/api/menu")
def menu():
    return {"name": RESTAURANT, "menu": MENU, "fee": DELIVERY_FEE, "free_above": FREE_DELIVERY_ABOVE, "min": MIN_ORDER}

@app.post("/api/order")
def place(o: NewOrder):
    phone = "".join(ch for ch in o.phone if ch.isdigit())[-10:]
    if len(phone) != 10 or not o.name.strip() or len(o.address.strip()) < 8:
        raise HTTPException(400, "Naam, 10-digit phone aur poora address zaroori hai")
    if o.pay not in ("Cash on Delivery", "UPI on Delivery"):
        raise HTTPException(400, "Galat payment option")
    prices = {m["id"]: m for m in MENU}
    total, parts = 0, []
    for l in o.items:
        if l.id not in prices or not (1 <= l.qty <= 20):
            raise HTTPException(400, "Galat item")
        total += prices[l.id]["p"] * l.qty
        parts.append(f'{prices[l.id]["n"]} x{l.qty}')
    if not parts or len(parts) > 30:
        raise HTTPException(400, "Cart khali hai")
    if total < MIN_ORDER:
        raise HTTPException(400, f"Minimum order Rs {MIN_ORDER} ka hai")
    total += 0 if total >= FREE_DELIVERY_ABOVE else DELIVERY_FEE
    with Session() as s:
        r = Order(name=o.name.strip()[:80], phone=phone, address=o.address.strip()[:300],
                  items=", ".join(parts), total=total, pay=o.pay)
        s.add(r); s.commit()
        return {"id": r.id, "total": total}

@app.get("/api/order/{oid}")
def track(oid: int, phone: str):
    p = "".join(ch for ch in phone if ch.isdigit())[-10:]
    with Session() as s:
        r = s.get(Order, oid)
        if not r or r.phone != p:
            raise HTTPException(404, "Order nahi mila")
        return {"id": r.id, "items": r.items, "total": r.total, "pay": r.pay, "status": r.status}

@app.post("/api/owner/login")
def login(l: Login, request: Request):
    ip = request.client.host if request.client else "x"
    n, t = fails.get(ip, (0, 0))
    if n >= 5 and time.time() - t < 300:
        raise HTTPException(429, "Bahut galat try. 5 minute baad try karein")
    if not OWNER_PASSWORD or not hmac.compare_digest(l.password, OWNER_PASSWORD):
        fails[ip] = (n + 1, time.time())
        raise HTTPException(401, "Galat password")
    fails.pop(ip, None)
    return {"token": make_token()}

@app.get("/api/owner/orders")
def orders(authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        rows = s.query(Order).order_by(Order.id.desc()).limit(100).all()
        return [{"id": r.id, "name": r.name, "phone": r.phone, "address": r.address, "items": r.items,
                 "total": r.total, "pay": r.pay, "status": r.status,
                 "time": r.created.isoformat() + "Z"} for r in rows]

@app.post("/api/owner/status")
def set_status(d: SetStatus, authorization: str = Header(None)):
    check_token(authorization)
    if d.status not in STATUSES:
        raise HTTPException(400, "Galat status")
    with Session() as s:
        r = s.get(Order, d.id)
        if not r:
            raise HTTPException(404, "Order nahi mila")
        r.status = d.status; s.commit()
    return {"ok": True}

@app.get("/owner")
def owner_page():
    return FileResponse("static/owner.html")
@app.get("/manifest.json")
def manifest():
    return {"name": RESTAURANT, "short_name": RESTAURANT, "start_url": "/", "display": "standalone",
            "background_color": "#006491", "theme_color": "#006491",
            "icons": [{"src": "/static/icon.svg", "sizes": "any", "type": "image/svg+xml"}]}
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
def home():
    return FileResponse("static/index.html")
