from html import escape as hx
import os, re, json, threading, time, hmac, hashlib, base64, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text, create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------- DEFAULT SETTINGS (baad mein owner page se badal sakte ho) ----------
RESTAURANT = os.getenv("RESTAURANT_NAME", "Quick Bite")
DELIVERY_FEE = int(os.getenv("DELIVERY_FEE", "30"))
FREE_DELIVERY_ABOVE = int(os.getenv("FREE_DELIVERY_ABOVE", "299"))
MIN_ORDER = int(os.getenv("MIN_ORDER", "99"))
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "")
UPI_ID = os.getenv("UPI_ID", "").strip()
MC_ID = os.getenv("MC_CUSTOMER_ID", "").strip()
MC_PASS = os.getenv("MC_PASSWORD", "")
MC_EMAIL = os.getenv("MC_EMAIL", "").strip()
OTP_ON = bool(MC_ID and MC_PASS)
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24).hex())
BASE = os.path.dirname(os.path.abspath(__file__))
def page(name):
    for p in (os.path.join(BASE, name), os.path.join(BASE, "static", name)):
        if os.path.exists(p):
            return p
    return os.path.join(BASE, "static", name)

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
DEFAULTS = {"name": RESTAURANT, "banner": "Garam Garam, Fast Delivery ⚡",
            "sub": "Momos • Chowmein • Fries • Chilli Potato", "eta": "30-40 min", "city": "", "shop_phone": "", "shop_address": "", "fee": str(DELIVERY_FEE),
            "free_above": str(FREE_DELIVERY_ABOVE), "min": str(MIN_ORDER), "upi": UPI_ID, "open": "1"}

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
    lat = Column(Float); lng = Column(Float)
    pay_status = Column(String(20), default="COD")
    coupon = Column(String(30)); discount = Column(Float)

class Dish(Base):
    __tablename__ = "dishes"
    id = Column(Integer, primary_key=True)
    name = Column(String(120)); cat = Column(String(60)); price = Column(Float)
    descr = Column(Text); emoji = Column(String(10)); veg = Column(Integer, default=1)
    avail = Column(Integer, default=1)
    variants = Column(Text)

class Coupon(Base):
    __tablename__ = "coupons"
    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True); kind = Column(String(10)); value = Column(Float)
    min_order = Column(Float, default=0); active = Column(Integer, default=1)

class Otp(Base):
    __tablename__ = "otps"
    phone = Column(String(15), primary_key=True)
    code_hash = Column(String(80)); exp = Column(Float); tries = Column(Integer, default=0)
    sent = Column(Integer, default=0); win = Column(Float, default=0)

class Setting(Base):
    __tablename__ = "settings"
    k = Column(String(40), primary_key=True); v = Column(Text)

for _i in range(15):
    try:
        Base.metadata.create_all(engine)
        break
    except Exception as e:
        print("DB not ready, retrying...", e)
        time.sleep(4)
else:
    Base.metadata.create_all(engine)
for _c, _t in (("lat", "FLOAT"), ("lng", "FLOAT"), ("pay_status", "VARCHAR(20)"),
               ("coupon", "VARCHAR(30)"), ("discount", "FLOAT")):
    try:
        with engine.begin() as _cn:
            _cn.execute(text("ALTER TABLE orders ADD COLUMN " + _c + " " + _t))
    except Exception:
        pass
try:
    with engine.begin() as _cn:
        _cn.execute(text("ALTER TABLE dishes ADD COLUMN variants TEXT"))
except Exception:
    pass
with Session() as _s:
    if _s.query(Dish).count() == 0:
        for m in MENU:
            _s.add(Dish(name=m["n"], cat=m["c"], price=m["p"], descr=m["d"], emoji=m["e"], veg=m["v"], avail=1))
        _s.commit()

def get_settings(s):
    d = dict(DEFAULTS)
    for r in s.query(Setting).all():
        d[r.k] = r.v
    return d
def num(x):
    try:
        return int(float(x))
    except Exception:
        return 0
def money(x):
    return int(x) if float(x) == int(x) else float(x)

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

def user_token(phone):
    exp = str(int(time.time()) + 30 * 24 * 3600)
    return phone + "." + exp + "." + hmac.new(SECRET_KEY.encode(), (phone + "." + exp).encode(), hashlib.sha256).hexdigest()
def user_token_ok(tok, phone):
    try:
        p, exp, sig = (tok or "").split(".")
        good = hmac.new(SECRET_KEY.encode(), (p + "." + exp).encode(), hashlib.sha256).hexdigest()
        return p == phone and hmac.compare_digest(sig, good) and int(exp) > time.time()
    except Exception:
        return False
_mc = {"tok": None, "t": 0}
def mc_call(method, path, params, token=None):
    url = "https://cpaas.messagecentral.com" + path + "?" + urllib.parse.urlencode(params)
    headers = {"accept": "*/*"}
    if token:
        headers["authToken"] = token
    req = urllib.request.Request(url, method=method, headers=headers, data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {}
    except Exception:
        return {}
def mc_token(force=False):
    if not force and _mc["tok"] and time.time() - _mc["t"] < 3000:
        return _mc["tok"]
    p = {"customerId": MC_ID, "key": base64.b64encode(MC_PASS.encode()).decode(), "scope": "NEW", "country": "91"}
    if MC_EMAIL:
        p["email"] = MC_EMAIL
    d = mc_call("GET", "/auth/v1/authentication/token", p)
    _mc["tok"] = d.get("token"); _mc["t"] = time.time()
    return _mc["tok"]
def mc_send(phone):
    for force in (False, True):
        tok = mc_token(force)
        if not tok:
            continue
        d = mc_call("POST", "/verification/v3/send", {"countryCode": "91", "flowType": "SMS", "mobileNumber": phone, "otpLength": "6"}, tok)
        vid = (d.get("data") or {}).get("verificationId")
        if d.get("responseCode") == 200 and vid:
            return str(vid), ""
        if d.get("message") in ("REQUEST_ALREADY_EXISTS",) or d.get("responseCode") == 506:
            return None, "Pehle bheja hua OTP abhi valid hai. 1 minute baad dobara try karein"
    return None, "OTP bhej nahi paye. Thodi der baad try karein"
def mc_check(vid, code):
    tok = mc_token()
    d = mc_call("GET", "/verification/v3/validateOtp", {"verificationId": vid, "code": code}, tok)
    if (d.get("data") or {}).get("verificationStatus") == "VERIFICATION_COMPLETED" and d.get("responseCode") == 200:
        return True
    return False

def tg_creds():
    with Session() as s:
        t = s.get(Setting, "tg_token"); c = s.get(Setting, "tg_chat")
        return (t.v if t else ""), (c.v if c else "")
def tg_send(text):
    tok, chat = tg_creds()
    if not tok or not chat:
        return False
    try:
        req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % tok, method="POST",
                                     data=json.dumps({"chat_id": chat, "text": text, "disable_web_page_preview": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return bool(json.loads(r.read().decode()).get("ok"))
    except Exception:
        return False
def remind(oid, n):
    with Session() as s:
        o = s.get(Order, oid)
        if not o or o.status != "Received":
            return
        text = "⚠️ Order #%d abhi tak accept nahi hua (%s, Rs %d). Jaldi dekhein!" % (o.id, o.name, int(o.total or 0))
    tg_send(text)
    if n < 3:
        t = threading.Timer(120, remind, args=(oid, n + 1)); t.daemon = True; t.start()

def seo_html(src, S, dishes, base):
    name = S["name"]; city = (S.get("city") or "").strip()
    cats = []
    for d in dishes:
        if d.cat not in cats:
            cats.append(d.cat)
    where = (" in " + city) if city else ""
    title = "%s - Online Food Order & Home Delivery%s" % (name, where)
    desc = ("%s: %s. Order online with fast home delivery%s. Cash on Delivery and UPI payment." % (name, ", ".join(cats[:5]), where))[:300]
    ld = {"@context": "https://schema.org", "@type": "Restaurant", "name": name, "url": base + "/",
          "servesCuisine": cats[:6], "priceRange": "Rs",
          "hasMenu": {"@type": "Menu", "hasMenuSection": [
              {"@type": "MenuSection", "name": c, "hasMenuItem": [
                  {"@type": "MenuItem", "name": d.name, "offers": {"@type": "Offer", "price": str(int(d.price)), "priceCurrency": "INR"}}
                  for d in dishes if d.cat == c]} for c in cats]}}
    ph = "".join(ch for ch in (S.get("shop_phone") or "") if ch.isdigit())[-10:]
    if len(ph) == 10:
        ld["telephone"] = "+91" + ph
    if city or S.get("shop_address"):
        ld["address"] = {"@type": "PostalAddress", "streetAddress": S.get("shop_address") or "",
                         "addressLocality": city, "addressCountry": "IN"}
    head = ('<title>%s</title>\n<meta name="description" content="%s">\n<link rel="canonical" href="%s/">\n'
            '<link rel="icon" href="/static/icon.svg" type="image/svg+xml">\n'
            '<meta property="og:type" content="restaurant.restaurant"><meta property="og:title" content="%s">'
            '<meta property="og:description" content="%s"><meta property="og:url" content="%s/">'
            '<meta property="og:site_name" content="%s"><meta name="twitter:card" content="summary">\n'
            '<script type="application/ld+json">%s</script>') % (
        hx(title), hx(desc), hx(base), hx(title), hx(desc), hx(base), hx(name),
        json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))
    rows = ""
    for c in cats:
        rows += "<p><b>%s:</b> %s</p>" % (hx(c), " &middot; ".join("%s &#8377;%d" % (hx(d.name), int(d.price)) for d in dishes if d.cat == c))
    foot = ('<section id="seo-menu" style="max-width:640px;margin:26px auto 10px;padding:0 14px;font-size:12px;color:var(--mu);line-height:1.6">'
            '<h2 style="font-size:14px;margin-bottom:6px">%s - Menu &amp; Prices%s</h2>%s</section>') % (hx(name), hx(where), rows)
    out = re.sub(r"<title>.*?</title>", lambda x: head, src, count=1, flags=re.S)
    out = out.replace('<html lang="en">', '<html lang="en-IN">', 1)
    return out.replace("</main>", "</main>\n" + foot, 1)

def site_base(request):
    host = request.headers.get("host", "")
    return ("http://" if host.startswith(("localhost", "127.")) else "https://") + host

app = FastAPI(title=RESTAURANT)

class Line(BaseModel):
    id: int
    qty: int
    v: Optional[int] = None
class NewOrder(BaseModel):
    name: str; phone: str; address: str; pay: str; items: List[Line]
    lat: Optional[float] = None
    lng: Optional[float] = None
    coupon: Optional[str] = None
    token: Optional[str] = None
class OtpSend(BaseModel):
    phone: str
class OtpVerify(BaseModel):
    phone: str; code: str
class Login(BaseModel):
    password: str
class SetStatus(BaseModel):
    id: int; status: str
class DelId(BaseModel):
    id: int
class VarIn(BaseModel):
    l: str; p: float
class DishIn(BaseModel):
    id: Optional[int] = None
    name: str; cat: str; price: float = 0
    variants: List[VarIn] = []
    descr: str = ""; emoji: str = "🍽️"; veg: int = 1
class CouponIn(BaseModel):
    code: str; kind: str; value: float; min_order: float = 0
class CouponCheck(BaseModel):
    code: str; subtotal: float
class TgIn(BaseModel):
    token: str
class SettingsIn(BaseModel):
    name: str; banner: str; sub: str; eta: str = ""; city: str = ""; shop_phone: str = ""; shop_address: str = ""; fee: float; free_above: float; min: float; upi: str; open: int

def calc_coupon(s, code, subtotal):
    c = s.query(Coupon).filter(Coupon.code == code.strip().upper(), Coupon.active == 1).first()
    if not c:
        raise HTTPException(400, "Ye coupon sahi nahi hai")
    if subtotal < c.min_order:
        raise HTTPException(400, "Is coupon ke liye minimum Rs %d ka order chahiye" % int(c.min_order))
    d = subtotal * c.value / 100 if c.kind == "percent" else c.value
    d = int(round(min(d, subtotal)))
    label = ("%d%% off" % int(c.value)) if c.kind == "percent" else ("Rs %d off" % int(c.value))
    return d, label

# ---------- CUSTOMER API ----------
@app.get("/api/menu")
def menu():
    with Session() as s:
        S = get_settings(s)
        dishes = s.query(Dish).order_by(Dish.id).all()
        return {"name": S["name"], "banner": S["banner"], "sub": S["sub"], "eta": S["eta"], "open": S["open"],
                "fee": num(S["fee"]), "free_above": num(S["free_above"]), "min": num(S["min"]), "upi": S["upi"], "otp": OTP_ON,
                "menu": [{"id": d.id, "n": d.name, "c": d.cat, "p": money(d.price), "e": d.emoji or "🍽️",
                          "v": d.veg, "d": d.descr or "", "a": d.avail,
                          "vs": json.loads(d.variants or "[]")} for d in dishes]}

@app.post("/api/coupon/check")
def coupon_check(c: CouponCheck):
    with Session() as s:
        d, label = calc_coupon(s, c.code, c.subtotal)
        return {"discount": d, "label": label}

@app.post("/api/otp/send")
def otp_send(d: OtpSend):
    if not OTP_ON:
        raise HTTPException(400, "OTP service chalu nahi hai")
    phone = "".join(ch for ch in d.phone if ch.isdigit())[-10:]
    if len(phone) != 10:
        raise HTTPException(400, "Sahi 10-digit number daalein")
    now = time.time()
    with Session() as s:
        r = s.get(Otp, phone)
        if not r:
            r = Otp(phone=phone, sent=0, win=now, tries=0); s.add(r)
        if now - (r.win or 0) > 600:
            r.sent = 0; r.win = now
        if (r.sent or 0) >= 3:
            raise HTTPException(429, "Bahut baar OTP maanga. 10 minute baad try karein")
        vid, err = mc_send(phone)
        if not vid:
            raise HTTPException(502, err)
        r.code_hash = vid; r.exp = now + 300; r.tries = 0; r.sent = (r.sent or 0) + 1
        s.commit()
    return {"ok": True}

@app.post("/api/otp/verify")
def otp_verify(d: OtpVerify):
    phone = "".join(ch for ch in d.phone if ch.isdigit())[-10:]
    with Session() as s:
        r = s.get(Otp, phone)
        if not r or not r.code_hash or (r.exp or 0) < time.time():
            raise HTTPException(400, "OTP expire ho gaya. Naya OTP mangayein")
        if (r.tries or 0) >= 5:
            raise HTTPException(429, "Bahut galat try. Naya OTP mangayein")
        r.tries = (r.tries or 0) + 1
        if not mc_check(r.code_hash, d.code.strip()):
            s.commit()
            raise HTTPException(400, "OTP galat hai")
        r.code_hash = None; s.commit()
    return {"token": user_token(phone)}

@app.post("/api/order")
def place(o: NewOrder):
    phone = "".join(ch for ch in o.phone if ch.isdigit())[-10:]
    if len(phone) != 10 or not o.name.strip() or len(o.address.strip()) < 8:
        raise HTTPException(400, "Naam, 10-digit phone aur poora address zaroori hai")
    if OTP_ON and not user_token_ok(o.token, phone):
        raise HTTPException(401, "Pehle phone number OTP se verify karein")
    with Session() as s:
        S = get_settings(s)
        if S["open"] != "1":
            raise HTTPException(400, "Restaurant abhi band hai")
        if o.pay not in ("Cash on Delivery", "Pay Now (UPI)") or (o.pay == "Pay Now (UPI)" and not S["upi"]):
            raise HTTPException(400, "Galat payment option")
        dishes = {d.id: d for d in s.query(Dish).all()}
        sub, parts = 0, []
        for l in o.items:
            d = dishes.get(l.id)
            if not d or not (1 <= l.qty <= 20):
                raise HTTPException(400, "Galat item")
            if not d.avail:
                raise HTTPException(400, d.name + " abhi available nahi hai")
            vs = json.loads(d.variants or "[]")
            if vs:
                if l.v is None or not (0 <= l.v < len(vs)):
                    raise HTTPException(400, d.name + ": Half/Full chuniye")
                price, label = vs[l.v]["p"], "%s (%s)" % (d.name, vs[l.v]["l"])
            else:
                price, label = d.price, d.name
            sub += price * l.qty
            parts.append("%s x%d" % (label, l.qty))
        if not parts or len(parts) > 30:
            raise HTTPException(400, "Cart khali hai")
        if sub < num(S["min"]):
            raise HTTPException(400, "Minimum order Rs %d ka hai" % num(S["min"]))
        disc, code = 0, None
        if o.coupon and o.coupon.strip():
            disc, _ = calc_coupon(s, o.coupon, sub)
            code = o.coupon.strip().upper()
        base = sub - disc
        total = base + (0 if base >= num(S["free_above"]) else num(S["fee"]))
        r = Order(name=o.name.strip()[:80], phone=phone, address=o.address.strip()[:300],
                  items=", ".join(parts), total=total, pay=o.pay,
                  pay_status="COD" if o.pay == "Cash on Delivery" else "Unpaid",
                  lat=o.lat if o.lat is not None and -90 <= o.lat <= 90 else None,
                  lng=o.lng if o.lng is not None and -180 <= o.lng <= 180 else None,
                  coupon=code, discount=disc)
        s.add(r); s.commit()
        oid = r.id
        mp = ("https://www.google.com/maps?q=%s,%s" % (r.lat, r.lng)) if r.lat is not None and r.lng is not None else \
             ("https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(r.address))
        text = "🆕 NAYA ORDER #%d\n💰 Rs %d (%s)\n👤 %s · %s\n🍽️ %s\n📍 %s\n🗺️ %s" % (
            oid, int(total), o.pay, r.name, phone, r.items, r.address, mp)
    threading.Thread(target=tg_send, args=(text,), daemon=True).start()
    t = threading.Timer(120, remind, args=(oid, 1)); t.daemon = True; t.start()
    return {"id": oid, "total": total}

@app.get("/api/order/{oid}")
def track(oid: int, phone: str):
    p = "".join(ch for ch in phone if ch.isdigit())[-10:]
    with Session() as s:
        r = s.get(Order, oid)
        if not r or r.phone != p:
            raise HTTPException(404, "Order nahi mila")
        return {"id": r.id, "items": r.items, "total": r.total, "pay": r.pay, "status": r.status, "pay_status": r.pay_status}

@app.post("/api/order/{oid}/claim")
def claim(oid: int, phone: str):
    p = "".join(ch for ch in phone if ch.isdigit())[-10:]
    with Session() as s:
        r = s.get(Order, oid)
        if not r or r.phone != p:
            raise HTTPException(404, "Order nahi mila")
        if r.pay_status == "Unpaid":
            r.pay_status = "Claimed"; s.commit()
    return {"ok": True}

# ---------- OWNER API ----------
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
                 "total": r.total, "pay": r.pay, "status": r.status, "pay_status": r.pay_status,
                 "lat": r.lat, "lng": r.lng, "coupon": r.coupon, "discount": r.discount,
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

@app.post("/api/owner/paid")
def mark_paid(d: SetStatus, authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        r = s.get(Order, d.id)
        if not r:
            raise HTTPException(404, "Order nahi mila")
        r.pay_status = "Paid"; s.commit()
    return {"ok": True}

@app.get("/api/owner/dishes")
def o_dishes(authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        return [{"id": d.id, "name": d.name, "cat": d.cat, "price": money(d.price), "descr": d.descr or "",
                 "emoji": d.emoji or "", "veg": d.veg, "avail": d.avail,
                 "vs": json.loads(d.variants or "[]")} for d in s.query(Dish).order_by(Dish.cat, Dish.id).all()]

@app.post("/api/owner/dish")
def o_dish_save(d: DishIn, authorization: str = Header(None)):
    check_token(authorization)
    vs = [{"l": v.l.strip()[:20], "p": v.p} for v in d.variants if v.l.strip() and 1 <= v.p <= 100000][:3]
    price = min(v["p"] for v in vs) if vs else d.price
    if not d.name.strip() or not d.cat.strip() or not (1 <= price <= 100000):
        raise HTTPException(400, "Naam, category aur sahi price daalein")
    with Session() as s:
        if d.id:
            r = s.get(Dish, d.id)
            if not r:
                raise HTTPException(404, "Dish nahi mili")
        else:
            r = Dish(avail=1); s.add(r)
        r.name = d.name.strip()[:120]; r.cat = d.cat.strip()[:60]; r.price = price
        r.variants = json.dumps(vs, ensure_ascii=False) if vs else None
        r.descr = d.descr.strip()[:300]; r.emoji = (d.emoji.strip() or "🍽️")[:8]; r.veg = 1 if d.veg else 0
        s.commit()
    return {"ok": True}

@app.post("/api/owner/dish/toggle")
def o_dish_toggle(d: DelId, authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        r = s.get(Dish, d.id)
        if not r:
            raise HTTPException(404, "Dish nahi mili")
        r.avail = 0 if r.avail else 1; s.commit()
    return {"ok": True}

@app.post("/api/owner/dish/delete")
def o_dish_delete(d: DelId, authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        r = s.get(Dish, d.id)
        if r:
            s.delete(r); s.commit()
    return {"ok": True}

@app.get("/api/owner/coupons")
def o_coupons(authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        return [{"id": c.id, "code": c.code, "kind": c.kind, "value": money(c.value),
                 "min_order": money(c.min_order or 0), "active": c.active} for c in s.query(Coupon).order_by(Coupon.id.desc()).all()]

@app.post("/api/owner/coupon")
def o_coupon_add(c: CouponIn, authorization: str = Header(None)):
    check_token(authorization)
    code = "".join(ch for ch in c.code.upper() if ch.isalnum())[:30]
    if not code or c.kind not in ("percent", "flat") or c.value <= 0 or (c.kind == "percent" and c.value > 90):
        raise HTTPException(400, "Coupon details sahi nahi hain (percent 90 se kam hona chahiye)")
    with Session() as s:
        if s.query(Coupon).filter(Coupon.code == code).first():
            raise HTTPException(400, "Ye coupon code pehle se hai")
        s.add(Coupon(code=code, kind=c.kind, value=c.value, min_order=max(c.min_order, 0), active=1)); s.commit()
    return {"ok": True}

@app.post("/api/owner/coupon/toggle")
def o_coupon_toggle(d: DelId, authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        r = s.get(Coupon, d.id)
        if r:
            r.active = 0 if r.active else 1; s.commit()
    return {"ok": True}

@app.post("/api/owner/coupon/delete")
def o_coupon_delete(d: DelId, authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        r = s.get(Coupon, d.id)
        if r:
            s.delete(r); s.commit()
    return {"ok": True}

@app.get("/api/owner/settings")
def o_settings(authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        S = get_settings(s)
        return {"name": S["name"], "banner": S["banner"], "sub": S["sub"], "eta": S["eta"], "city": S["city"], "shop_phone": S["shop_phone"],
                "shop_address": S["shop_address"], "fee": num(S["fee"]),
                "free_above": num(S["free_above"]), "min": num(S["min"]), "upi": S["upi"], "open": int(S["open"])}

@app.post("/api/owner/settings")
def o_settings_save(d: SettingsIn, authorization: str = Header(None)):
    check_token(authorization)
    vals = {"name": d.name.strip()[:60] or RESTAURANT, "banner": d.banner.strip()[:80], "sub": d.sub.strip()[:120], "eta": d.eta.strip()[:30], "city": d.city.strip()[:40],
            "shop_phone": d.shop_phone.strip()[:15], "shop_address": d.shop_address.strip()[:150],
            "fee": str(int(max(d.fee, 0))), "free_above": str(int(max(d.free_above, 0))), "min": str(int(max(d.min, 0))),
            "upi": d.upi.strip()[:80], "open": "1" if d.open else "0"}
    with Session() as s:
        for k, v in vals.items():
            r = s.get(Setting, k)
            if r:
                r.v = v
            else:
                s.add(Setting(k=k, v=v))
        s.commit()
    return {"ok": True}

@app.get("/api/owner/telegram")
def o_tg_status(authorization: str = Header(None)):
    check_token(authorization)
    tok, chat = tg_creds()
    return {"connected": bool(tok and chat)}

@app.post("/api/owner/telegram")
def o_tg_connect(d: TgIn, authorization: str = Header(None)):
    check_token(authorization)
    tok = d.token.strip()
    if ":" not in tok or len(tok) < 20:
        raise HTTPException(400, "Bot token sahi nahi lag raha")
    try:
        with urllib.request.urlopen("https://api.telegram.org/bot%s/getUpdates" % tok, timeout=10) as r:
            data = json.loads(r.read().decode())
    except Exception:
        raise HTTPException(400, "Token galat hai ya Telegram se connect nahi hua")
    chat = None
    for u in reversed(data.get("result", [])):
        c = (u.get("message") or {}).get("chat") or {}
        if c.get("id"):
            chat = c["id"]; break
    if not chat:
        raise HTTPException(400, "Pehle Telegram mein apne bot ko kholke /start bhejein, phir dobara Connect dabayein")
    with Session() as s:
        for k, v in (("tg_token", tok), ("tg_chat", str(chat))):
            r = s.get(Setting, k)
            if r:
                r.v = v
            else:
                s.add(Setting(k=k, v=v))
        s.commit()
    tg_send("✅ Quick Bite alerts chalu ho gaye! Ab har naye order par yahan message aayega.")
    return {"ok": True}

@app.post("/api/owner/telegram/test")
def o_tg_test(authorization: str = Header(None)):
    check_token(authorization)
    if not tg_send("🔔 Test alert: Quick Bite se message aa raha hai."):
        raise HTTPException(400, "Alert nahi gaya. Dobara Connect karke dekhein")
    return {"ok": True}

@app.post("/api/owner/telegram/off")
def o_tg_off(authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        for k in ("tg_token", "tg_chat"):
            r = s.get(Setting, k)
            if r:
                s.delete(r)
        s.commit()
    return {"ok": True}

@app.get("/api/owner/report")
def o_report(authorization: str = Header(None)):
    check_token(authorization)
    with Session() as s:
        rows = s.query(Order).filter(Order.created >= datetime.utcnow() - timedelta(days=30)).all()
    days, top, cancelled = {}, {}, 0
    for r in rows:
        if r.status == "Cancelled":
            cancelled += 1
            continue
        k = (r.created + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")
        d = days.setdefault(k, {"orders": 0, "revenue": 0})
        d["orders"] += 1; d["revenue"] += int(r.total or 0)
        for part in (r.items or "").split(", "):
            if " x" in part:
                name, q = part.rsplit(" x", 1)
                try:
                    top[name] = top.get(name, 0) + int(q)
                except ValueError:
                    pass
    return {"today": (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d"),
            "days": [dict(date=k, **v) for k, v in sorted(days.items(), reverse=True)],
            "top": sorted(top.items(), key=lambda x: -x[1])[:8], "cancelled": cancelled}

@app.get("/owner")
def owner_page():
    return FileResponse(page("owner.html"))
@app.get("/manifest.json")
def manifest():
    return {"name": RESTAURANT, "short_name": RESTAURANT, "start_url": "/", "display": "standalone",
            "background_color": "#006491", "theme_color": "#006491",
            "icons": [{"src": "/static/icon.svg", "sizes": "any", "type": "image/svg+xml"}]}
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
@app.get("/")
def home(request: Request):
    with open(page("index.html"), encoding="utf-8") as f:
        src = f.read()
    try:
        with Session() as s:
            S = get_settings(s)
            dishes = s.query(Dish).filter(Dish.avail == 1).order_by(Dish.id).all()
            out = seo_html(src, S, dishes, site_base(request))
    except Exception as e:
        print("seo error", e)
        out = src
    return Response(content=out, media_type="text/html")

@app.get("/robots.txt")
def robots(request: Request):
    return PlainTextResponse("User-agent: *\nAllow: /\nDisallow: /owner\nDisallow: /api/\nSitemap: %s/sitemap.xml\n" % site_base(request))

@app.get("/sitemap.xml")
def sitemap(request: Request):
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>%s/</loc><changefreq>daily</changefreq><priority>1.0</priority></url></urlset>' % site_base(request)
    return Response(content=xml, media_type="application/xml")
