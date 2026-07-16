from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator, model_validator
import re, random, hashlib, calendar, secrets, smtplib, ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from datetime import date, datetime, timedelta, timezone
import asyncpg, os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional, Literal

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
DATABASE_URL      = os.getenv("DATABASE_URL")
SMTP_EMAIL        = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")

db_pool: asyncpg.Pool = None

# ── Email OTP Config ──────────────────────────────────────
OTP_EXPIRY_MINUTES          = 5
OTP_RESEND_COOLDOWN_SECONDS = 30
OTP_MAX_ATTEMPTS            = 5

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    print(f"[DEBUG] SMTP_EMAIL = {SMTP_EMAIL!r}")
    print(f"[DEBUG] SMTP_APP_PASSWORD set? = {bool(SMTP_APP_PASSWORD)} (length={len(SMTP_APP_PASSWORD) if SMTP_APP_PASSWORD else 0})")
    db_pool = await asyncpg.create_pool(
        dsn=DATABASE_URL, min_size=1, max_size=5,
        statement_cache_size=0, ssl="require",
    )
    yield
    if db_pool:
        await db_pool.close()

app = FastAPI(title="Pakistan Railway Ticketing API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── Stations & Trains ─────────────────────────────────────
STATIONS = [
    "Karachi City","Karachi Cantonment","Hyderabad","Nawabshah","Sukkur",
    "Bahawalpur","Khanewal","Sahiwal","Multan Cantonment","Faisalabad",
    "Lahore","Gujranwala","Sialkot","Sargodha","Rawalpindi","Margala",
    "Peshawar Cantonment","Peshawar City","Quetta",
]

TRAINS = [
    {"id":1, "name":"5UP - Green Line Express",      "time":"22:00","source":"Karachi Cantonment","destination":"Margala",
     "stops":["Karachi Cantonment","Hyderabad","Rohri","Bahawalpur","Khanewal","Lahore","Rawalpindi","Margala"],"price_factor":1.2},
    {"id":2, "name":"41UP - Karakoram Express",       "time":"15:30","source":"Karachi Cantonment","destination":"Lahore",
     "stops":["Karachi Cantonment","Hyderabad","Nawabshah","Sukkur","Bahawalpur","Khanewal","Sahiwal","Lahore"],"price_factor":1.0},
    {"id":3, "name":"33UP - Pak Business Express",    "time":"16:00","source":"Karachi Cantonment","destination":"Lahore",
     "stops":["Karachi Cantonment","Hyderabad","Sukkur","Multan Cantonment","Faisalabad","Lahore"],"price_factor":1.1},
    {"id":4, "name":"17UP - Millat Express",          "time":"14:15","source":"Karachi Cantonment","destination":"Sargodha",
     "stops":["Karachi Cantonment","Hyderabad","Nawabshah","Sukkur","Multan Cantonment","Khanewal","Faisalabad","Sargodha"],"price_factor":0.9},
    {"id":5, "name":"9UP - Allama Iqbal Express",     "time":"14:00","source":"Karachi Cantonment","destination":"Sialkot",
     "stops":["Karachi Cantonment","Hyderabad","Sukkur","Bahawalpur","Lahore","Gujranwala","Sialkot"],"price_factor":0.85},
    {"id":6, "name":"1UP - Khyber Mail",              "time":"22:15","source":"Karachi Cantonment","destination":"Peshawar City",
     "stops":["Karachi Cantonment","Hyderabad","Nawabshah","Sukkur","Multan Cantonment","Lahore","Rawalpindi","Margala","Peshawar Cantonment","Peshawar City"],"price_factor":0.95},
    {"id":7, "name":"6DN - Green Line Express",       "time":"20:00","source":"Margala","destination":"Karachi Cantonment",
     "stops":["Margala","Rawalpindi","Lahore","Khanewal","Bahawalpur","Rohri","Hyderabad","Karachi Cantonment"],"price_factor":1.2},
    {"id":8, "name":"42DN - Karakoram Express",       "time":"15:00","source":"Lahore","destination":"Karachi Cantonment",
     "stops":["Lahore","Sahiwal","Khanewal","Bahawalpur","Sukkur","Nawabshah","Hyderabad","Karachi Cantonment"],"price_factor":1.0},
    {"id":9, "name":"34DN - Pak Business Express",    "time":"16:30","source":"Lahore","destination":"Karachi Cantonment",
     "stops":["Lahore","Faisalabad","Multan Cantonment","Sukkur","Hyderabad","Karachi Cantonment"],"price_factor":1.1},
    {"id":10,"name":"18DN - Millat Express",          "time":"13:30","source":"Sargodha","destination":"Karachi Cantonment",
     "stops":["Sargodha","Faisalabad","Khanewal","Multan Cantonment","Sukkur","Nawabshah","Hyderabad","Karachi Cantonment"],"price_factor":0.9},
    {"id":11,"name":"10DN - Allama Iqbal Express",    "time":"12:00","source":"Sialkot","destination":"Karachi Cantonment",
     "stops":["Sialkot","Gujranwala","Lahore","Bahawalpur","Sukkur","Hyderabad","Karachi Cantonment"],"price_factor":0.85},
    {"id":12,"name":"2DN - Khyber Mail",              "time":"06:00","source":"Peshawar City","destination":"Karachi Cantonment",
     "stops":["Peshawar City","Peshawar Cantonment","Margala","Rawalpindi","Lahore","Multan Cantonment","Sukkur","Nawabshah","Hyderabad","Karachi Cantonment"],"price_factor":0.95},
    {"id":13,"name":"21UP - Lahore Express",          "time":"08:00","source":"Rawalpindi","destination":"Lahore",
     "stops":["Rawalpindi","Margala","Gujranwala","Lahore"],"price_factor":0.9},
    {"id":14,"name":"22DN - Lahore Express",          "time":"18:00","source":"Lahore","destination":"Rawalpindi",
     "stops":["Lahore","Gujranwala","Margala","Rawalpindi"],"price_factor":0.9},
    {"id":15,"name":"7UP - Awam Express",             "time":"10:00","source":"Karachi Cantonment","destination":"Quetta",
     "stops":["Karachi Cantonment","Hyderabad","Nawabshah","Sukkur","Quetta"],"price_factor":0.8},
    {"id":16,"name":"8DN - Awam Express",             "time":"09:00","source":"Quetta","destination":"Karachi Cantonment",
     "stops":["Quetta","Sukkur","Nawabshah","Hyderabad","Karachi Cantonment"],"price_factor":0.8},
    {"id":17,"name":"11UP - Peshawar Express",        "time":"07:30","source":"Rawalpindi","destination":"Peshawar City",
     "stops":["Rawalpindi","Margala","Peshawar Cantonment","Peshawar City"],"price_factor":0.85},
    {"id":18,"name":"12DN - Peshawar Express",        "time":"17:00","source":"Peshawar City","destination":"Rawalpindi",
     "stops":["Peshawar City","Peshawar Cantonment","Margala","Rawalpindi"],"price_factor":0.85},
    {"id":19,"name":"23UP - Chenab Express",          "time":"09:00","source":"Faisalabad","destination":"Lahore",
     "stops":["Faisalabad","Sahiwal","Lahore"],"price_factor":0.8},
    {"id":20,"name":"24DN - Chenab Express",          "time":"19:00","source":"Lahore","destination":"Faisalabad",
     "stops":["Lahore","Sahiwal","Faisalabad"],"price_factor":0.8},
]

# ── Seat & Pricing Config ─────────────────────────────────
CLASS_CONFIG = {
    "AC Business": {"coaches":["A1","A2"],          "cabins_per_coach":4,"berths_per_cabin":6,
                    "berth_labels":["1-Lower","2-Middle","3-Upper","4-Lower","5-Middle","6-Upper"]},
    "AC Standard": {"coaches":["B1","B2","B3"],     "cabins_per_coach":6,"berths_per_cabin":6,
                    "berth_labels":["1-Lower","2-Middle","3-Upper","4-Lower","5-Middle","6-Upper"]},
    "Economy":     {"coaches":["C1","C2","C3","C4"],"cabins_per_coach":8,"berths_per_cabin":6,
                    "berth_labels":["1-Lower","2-Middle","3-Upper","4-Lower","5-Middle","6-Upper"]},
}

BASE_CLASS_PRICES = {"AC Business":13250,"AC Standard":6500,"Economy":3500}
RABTA_CHARGE      = 10
REFUND_PERCENT    = 0.85

# ── Exclusive Routes ──────────────────────────────────────
EXCLUSIVE_ROUTES: dict[tuple[str,str], set[int]] = {
    ("karachi cantonment","margala"): {1},
    ("margala","karachi cantonment"): {7},
}

# ── Helpers ───────────────────────────────────────────────
def _get_booking_window() -> tuple[date, date]:
    today = date.today()
    month = today.month + 2
    year  = today.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    day   = min(today.day, calendar.monthrange(year, month)[1])
    return today, date(year, month, day)

def _is_route_exclusive(src: str, dst: str, train_id: int) -> bool:
    key = (src, dst)
    return train_id not in EXCLUSIVE_ROUTES[key] if key in EXCLUSIVE_ROUTES else False

def _validate_future_date(travel_date: str) -> date:
    try:
        d = datetime.strptime(travel_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    today, max_date = _get_booking_window()
    if d < today:
        raise HTTPException(400, "Travel date cannot be in the past.")
    if d > max_date:
        raise HTTPException(400, f"Bookings available up to 2 months in advance. Max: {max_date.strftime('%d %b %Y')}.")
    return d

def _get_train(train_id: int) -> dict:
    t = next((t for t in TRAINS if t["id"] == train_id), None)
    if not t:
        raise HTTPException(404, "Train not found.")
    return t

def _calc_fare(selected_class: str, price_factor: float, passenger_type: str) -> int:
    base = BASE_CLASS_PRICES.get(selected_class, 0) * price_factor
    if passenger_type == "Child":
        base /= 2
    return round(base)

# ── DB Helpers ────────────────────────────────────────────
async def _get_booked_seats_db(train_id: int, travel_date: date, selected_class: str) -> set:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT seat_number FROM seat_availability WHERE train_id=$1 AND travel_date=$2 AND selected_class=$3 AND is_booked=TRUE",
            train_id, travel_date, selected_class
        )
    return {r["seat_number"] for r in rows}

def _build_seat_layout(train_id: int, travel_date: date, selected_class: str, booked: set) -> list:
    config = CLASS_CONFIG.get(selected_class)
    if not config:
        return []
    date_str = travel_date.isoformat()
    cabins   = []
    for coach in config["coaches"]:
        for cabin_num in range(1, config["cabins_per_coach"] + 1):
            berths = []
            for berth in config["berth_labels"]:
                label = f"{coach}-Cabin{cabin_num}-{berth}"
                if label in booked:
                    available = False
                else:
                    seed      = int(hashlib.md5(f"seat_avail_{train_id}_{date_str}_{label}".encode()).hexdigest(), 16) % 100
                    available = seed < 65
                berths.append({"label":label,"coach":coach,"cabin":cabin_num,"berth":berth,"available":available})
            cabins.append({"coach":coach,"cabin":cabin_num,"berths":berths})
    return cabins

async def _upsert_user(conn, email: str, full_name: str, phone: str):
    await conn.execute(
        """INSERT INTO users (email, full_name, phone) VALUES ($1,$2,$3)
           ON CONFLICT (email) DO UPDATE SET
             full_name  = CASE WHEN EXCLUDED.full_name  != '' THEN EXCLUDED.full_name  ELSE users.full_name  END,
             phone      = CASE WHEN EXCLUDED.phone      != '' THEN EXCLUDED.phone      ELSE users.phone      END,
             updated_at = NOW()""",
        email, full_name or "", phone or "",
    )

def _generate_otp() -> str:
    """4-digit numeric OTP, cryptographically random (0000-9999)."""
    return f"{secrets.randbelow(10000):04d}"

def _send_otp_email(to_email: str, name: str, otp_code: str, purpose: str):
    action  = "complete your account signup" if purpose == "SIGNUP" else "verify this login from a new device"
    subject = "Your Pakistan Railways verification code"
    greeting = f"Assalam-o-Alaikum {name}," if name else "Assalam-o-Alaikum,"
    body = f"""{greeting}

Your verification code to {action} on Pakistan Railways — Passenger Portal is:

    {otp_code}

This code is valid for {OTP_EXPIRY_MINUTES} minutes and can only be used once.

If you did not request this code, you can safely ignore this email — no changes will be made to your account.

— Pakistan Railways Passenger Portal
This is an automated message, please do not reply to this email.
"""
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise RuntimeError("SMTP_EMAIL / SMTP_APP_PASSWORD not configured on the server.")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = formataddr(("Pakistan Railways", SMTP_EMAIL))
    msg["To"]      = to_email

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

async def _create_and_send_otp(conn, email: str, name: str, purpose: str):
    """Generates a fresh OTP, stores it, and emails it — with a resend cooldown."""
    last = await conn.fetchrow(
        "SELECT created_at FROM email_otps WHERE email=$1 AND purpose=$2 ORDER BY created_at DESC LIMIT 1",
        email, purpose
    )
    if last:
        elapsed = (datetime.now(timezone.utc) - last["created_at"]).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            wait = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(429, f"Please wait {wait}s before requesting another code.")

    otp_code   = _generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
    await conn.execute(
        "INSERT INTO email_otps (email, otp_code, purpose, expires_at) VALUES ($1,$2,$3,$4)",
        email, otp_code, purpose, expires_at
    )
    try:
        _send_otp_email(email, name or "", otp_code, purpose)
    except Exception as e:
        raise HTTPException(500, f"Failed to send verification email: {str(e)}")

async def _insert_payment(conn, email: str, booking_id: str, amount: float,
                           payment_method: str, account_number: str = "",
                           card_last4: str = "", card_expiry: str = "", cvv: str = ""):
    txn_id = f"TXN-{random.randint(10000000,99999999)}"
    if payment_method in ("JazzCash","Easypaisa"):
        mobile, db_last4, cvv_hash = account_number, None, None
    else:
        mobile   = None
        db_last4 = card_last4[-4:] if card_last4 else None
        cvv_hash = hashlib.sha256(cvv.encode()).hexdigest() if cvv else None
    await conn.execute(
        """INSERT INTO payment_records
             (email_id,booking_id,amount,payment_method,transaction_id,mobile_number,card_last4,card_cvv_hash,status)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'SUCCESS')""",
        email, booking_id, amount, payment_method, txn_id, mobile, db_last4, cvv_hash,
    )

# ── Pydantic Models ───────────────────────────────────────
class AuthRequest(BaseModel):
    email:    str
    password: str
    name:     str = ""

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        v = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("Please provide a valid email address.")
        return v

class SignupRequest(BaseModel):
    email:    str
    password: str
    name:     str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        v = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("Valid email required.")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if not re.fullmatch(r"[A-Za-z ]{2,60}", v):
            raise ValueError("Name: English alphabets only (2–60 chars).")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        errors = []
        if len(v) < 8:                                                    errors.append("8+ characters")
        if not re.search(r"[A-Z]", v):                                   errors.append("uppercase letter")
        if not re.search(r"[0-9]", v):                                   errors.append("number")
        if not re.search(r"[!@#$%^&*()\-_=+\[\]{};':\"\\|,.<>/?`~]", v):errors.append("special character")
        if errors:
            raise ValueError("Password must contain: " + ", ".join(errors))
        return v

class LoginRequest(AuthRequest):
    device_id: str = ""

class OTPVerifyRequest(BaseModel):
    email:     str
    otp_code:  str
    purpose:   Literal["SIGNUP", "LOGIN"]
    device_id: str = ""
    name:      str = ""

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        return v.strip().lower()

    @field_validator("otp_code")
    @classmethod
    def validate_otp(cls, v):
        v = v.strip()
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError("Code must be 4 digits.")
        return v

class OTPResendRequest(BaseModel):
    email:   str
    purpose: Literal["SIGNUP", "LOGIN"]

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        return v.strip().lower()

class BookingData(BaseModel):
    passenger_name:  str
    passenger_cnic:  str
    passenger_phone: str
    passenger_type:  str
    train_id:        int
    travel_date:     str
    selected_class:  str
    seat_label:      str
    payment_method:  str = "Visa"
    account_number:  str = ""
    payment_pin:     str = ""
    cvv:             str = ""
    card_last4:      str = ""
    card_expiry:     str = ""
    user_source:     str = ""
    user_destination:str = ""
    email_id:        str = ""
    full_name:       str = ""

    @field_validator("passenger_name")
    @classmethod
    def val_name(cls, v):
        v = v.strip()
        if not re.fullmatch(r"[A-Za-z ]{2,60}", v):
            raise ValueError("Name must be English alphabets only (2–60 chars).")
        return v

    @field_validator("passenger_cnic")
    @classmethod
    def val_cnic(cls, v):
        if not re.fullmatch(r"\d{5}-\d{7}-\d", v.strip()):
            raise ValueError("CNIC format: XXXXX-XXXXXXX-X")
        return v.strip()

    @field_validator("passenger_phone")
    @classmethod
    def val_phone(cls, v):
        if not re.fullmatch(r"0\d{3}-\d{7}", v.strip()):
            raise ValueError("Phone format: 0XXX-XXXXXXX")
        return v.strip()

    @field_validator("payment_method")
    @classmethod
    def val_pm(cls, v):
        if v not in {"JazzCash","Easypaisa","MasterCard","Visa"}:
            raise ValueError("Invalid payment method.")
        return v

    @model_validator(mode="after")
    def val_payment_fields(self):
        pin = self.payment_pin.strip()
        if self.payment_method in ("JazzCash","Easypaisa"):
            if not re.fullmatch(r"03\d{9}", self.account_number.strip()):
                raise ValueError(f"{self.payment_method} number must be 11 digits starting with 03.")
            expected = 4 if self.payment_method == "JazzCash" else 5
            if not re.fullmatch(r"\d{" + str(expected) + r"}", pin):
                raise ValueError(f"{self.payment_method} PIN must be {expected} digits.")
        else:
            if not re.fullmatch(r"\d{2}/\d{2}", self.card_expiry.strip()):
                raise ValueError("Expiry must be MM/YY.")
            if not re.fullmatch(r"\d{4}", self.cvv.strip()):
                raise ValueError("CVV must be 4 digits.")
            if not re.fullmatch(r"\d{4}", pin):
                raise ValueError("Card PIN must be 4 digits.")
        return self

# ── Routes ────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/auth/signup")
async def auth_signup(data: AuthRequest):
    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id, is_verified FROM users WHERE email=$1", data.email)
        if existing and existing["is_verified"]:
            raise HTTPException(409, "Email already registered. Please login.")
        if not re.fullmatch(r"[A-Za-z ]{2,60}", data.name.strip()):
            raise HTTPException(400, "Name must be English alphabets only (2–60 chars).")
        pw_hash = hashlib.sha256(data.password.encode()).hexdigest()
        await conn.execute(
            """INSERT INTO users (email, password_hash, full_name, is_verified) VALUES ($1,$2,$3,FALSE)
               ON CONFLICT (email) DO UPDATE SET
                 password_hash = EXCLUDED.password_hash,
                 full_name     = EXCLUDED.full_name,
                 updated_at    = NOW()""",
            data.email, pw_hash, data.name.strip()
        )
        await _create_and_send_otp(conn, data.email, data.name.strip(), "SIGNUP")
    return {"status":"otp_required","email":data.email,"name":data.name.strip(),"purpose":"SIGNUP"}

@app.post("/auth/login")
async def auth_login(data: LoginRequest):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE email=$1", data.email)
        if not user:
            raise HTTPException(404, "No account found. Please sign up first.")
        if user["password_hash"] != hashlib.sha256(data.password.encode()).hexdigest():
            raise HTTPException(401, "Incorrect password / غلط پاس ورڈ")

        # Email never verified (e.g. abandoned signup) — verify it first
        if not user["is_verified"]:
            await _create_and_send_otp(conn, data.email, user["full_name"], "SIGNUP")
            return {"status":"otp_required","email":data.email,"name":user["full_name"] or "","purpose":"SIGNUP"}

        # Known/trusted device — skip OTP
        device_id = data.device_id.strip()
        if device_id:
            trusted = await conn.fetchrow(
                "SELECT id FROM trusted_devices WHERE email=$1 AND device_id=$2", data.email, device_id
            )
            if trusted:
                await conn.execute(
                    "UPDATE trusted_devices SET last_used_at=NOW() WHERE email=$1 AND device_id=$2",
                    data.email, device_id
                )
                return {"status":"ok","email":data.email,"name":user["full_name"] or ""}

        # New / unknown device — require OTP
        await _create_and_send_otp(conn, data.email, user["full_name"], "LOGIN")
    return {"status":"otp_required","email":data.email,"name":user["full_name"] or "","purpose":"LOGIN"}

@app.post("/auth/verify-otp")
async def auth_verify_otp(data: OTPVerifyRequest):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM email_otps WHERE email=$1 AND purpose=$2 AND is_used=FALSE
               ORDER BY created_at DESC LIMIT 1""",
            data.email, data.purpose
        )
        if not row:
            raise HTTPException(400, "No active code found. Please request a new one.")
        if row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "Code expired. Please request a new one.")
        if row["attempts"] >= OTP_MAX_ATTEMPTS:
            raise HTTPException(429, "Too many incorrect attempts. Please request a new code.")
        if row["otp_code"] != data.otp_code:
            await conn.execute("UPDATE email_otps SET attempts = attempts + 1 WHERE id=$1", row["id"])
            remaining = OTP_MAX_ATTEMPTS - (row["attempts"] + 1)
            raise HTTPException(400, f"Incorrect code. {max(remaining,0)} attempt(s) left.")

        await conn.execute("UPDATE email_otps SET is_used=TRUE WHERE id=$1", row["id"])

        if data.purpose == "SIGNUP":
            await conn.execute("UPDATE users SET is_verified=TRUE WHERE email=$1", data.email)

        user = await conn.fetchrow("SELECT full_name FROM users WHERE email=$1", data.email)

        device_id = data.device_id.strip()
        if device_id:
            await conn.execute(
                """INSERT INTO trusted_devices (email, device_id) VALUES ($1,$2)
                   ON CONFLICT (email, device_id) DO UPDATE SET last_used_at=NOW()""",
                data.email, device_id
            )
    return {"status":"ok","email":data.email,"name":(user["full_name"] if user else None) or data.name or ""}

@app.post("/auth/resend-otp")
async def auth_resend_otp(data: OTPResendRequest):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT full_name FROM users WHERE email=$1", data.email)
        if not user:
            raise HTTPException(404, "No account found for this email.")
        await _create_and_send_otp(conn, data.email, user["full_name"], data.purpose)
    return {"status":"sent","email":data.email}

@app.get("/get-stations")
def get_stations():
    return {"stations": sorted(STATIONS)}

@app.get("/get-booking-window")
def get_booking_window():
    today, max_date = _get_booking_window()
    return {"today":today.isoformat(),"max_date":max_date.isoformat(),"max_date_display":max_date.strftime("%d %b %Y")}

@app.get("/search-trains")
def search_trains(source: str = Query(...), destination: str = Query(...), travel_date: str = Query(...)):
    d       = _validate_future_date(travel_date)
    s_lower = [s.lower() for s in STATIONS]
    if source.lower() not in s_lower:
        raise HTTPException(404, f"Station '{source}' not found.")
    if destination.lower() not in s_lower:
        raise HTTPException(404, f"Station '{destination}' not found.")
    if source.lower() == destination.lower():
        raise HTTPException(400, "Source and destination cannot be the same.")

    matched = []
    for train in TRAINS:
        if _is_route_exclusive(source.lower(), destination.lower(), train["id"]):
            continue
        stops_lower = [s.lower() for s in train["stops"]]
        if source.lower() in stops_lower and destination.lower() in stops_lower:
            si = stops_lower.index(source.lower())
            di = stops_lower.index(destination.lower())
            if si < di:
                days_ahead  = (d - date.today()).days
                avail_label = "Available" if days_ahead <= 7 else ("Limited Seats" if days_ahead <= 21 else "Booking Open")
                matched.append({
                    "id":train["id"],"name":train["name"],"time":train["time"],
                    "source":train["stops"][si],"destination":train["stops"][di],
                    "price_factor":train["price_factor"],"avail_label":avail_label,"days_ahead":days_ahead,
                })
    return {"trains":matched,"travel_date":travel_date,"count":len(matched)}

@app.get("/get-seats")
async def get_seats(train_id: int, selected_class: str, travel_date: str):
    d = _validate_future_date(travel_date)
    _get_train(train_id)
    if selected_class not in CLASS_CONFIG:
        raise HTTPException(400, "Invalid class.")
    booked  = await _get_booked_seats_db(train_id, d, selected_class)
    cabins  = _build_seat_layout(train_id, d, selected_class, booked)
    cfg     = CLASS_CONFIG[selected_class]
    return {"cabins":cabins,"class":selected_class,"config":{"coaches":cfg["coaches"],"cabins_per_coach":cfg["cabins_per_coach"],"berths_per_cabin":cfg["berths_per_cabin"]}}

@app.post("/confirm-booking")
async def confirm_booking(data: BookingData):
    d     = _validate_future_date(data.travel_date)
    train = _get_train(data.train_id)
    fare  = _calc_fare(data.selected_class, train["price_factor"], data.passenger_type)
    total = fare + RABTA_CHARGE
    coach = data.seat_label.split("-")[0]
    pnr        = f"PR-{random.randint(100000,999999)}"
    booking_id = f"BK-{random.randint(1000000,9999999)}"
    user_source  = data.user_source.strip()      or train["source"]
    user_dest    = data.user_destination.strip()  or train["destination"]
    ticket_route = f"{user_source} → {user_dest}"
    train_route  = f"{train['source']} → {train['destination']}"
    email        = data.email_id or "guest@railway.pk"

    async with db_pool.acquire() as conn:

        # ── Seat already booked check ──
        if await conn.fetchrow(
            "SELECT id FROM seat_availability WHERE train_id=$1 AND travel_date=$2 AND coach=$3 AND seat_number=$4 AND is_booked=TRUE",
            data.train_id, d, coach, data.seat_label
        ):
            raise HTTPException(409, "This seat is already booked. Please select another seat.")

        # ── Duplicate CNIC check — same CNIC + same train + same date ──
        if await conn.fetchrow(
            "SELECT booking_id FROM bookings WHERE passenger_cnic=$1 AND train_id=$2 AND travel_date=$3 AND status='CONFIRMED'",
            data.passenger_cnic, data.train_id, d
        ):
            raise HTTPException(409, "The train is already booked at this CNIC")

        async with conn.transaction():
            await _upsert_user(conn, email=email, full_name=data.full_name or data.passenger_name, phone=data.passenger_phone)
            await conn.execute(
                """INSERT INTO bookings
                     (booking_id,pnr,train_id,train_name,train_route,travel_date,train_time,
                      passenger_name,passenger_cnic,passenger_phone,passenger_type,
                      user_source,user_destination,ticket_route,
                      selected_class,coach,seat_label,fare,rabta_charge,total,email_id,status)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,'CONFIRMED')""",
                booking_id,pnr,data.train_id,train["name"],train_route,d,train["time"],
                data.passenger_name,data.passenger_cnic,data.passenger_phone,data.passenger_type,
                user_source,user_dest,ticket_route,
                data.selected_class,coach,data.seat_label,fare,RABTA_CHARGE,total,email,
            )
            await conn.execute(
                """INSERT INTO seat_availability
                     (train_id,travel_date,selected_class,coach,seat_number,is_booked,booked_by_email,booked_at)
                   VALUES ($1,$2,$3,$4,$5,TRUE,$6,NOW())
                   ON CONFLICT (train_id,travel_date,coach,seat_number)
                   DO UPDATE SET is_booked=TRUE,booked_by_email=EXCLUDED.booked_by_email,booked_at=NOW()""",
                data.train_id,d,data.selected_class,coach,data.seat_label,email,
            )
            await _insert_payment(
                conn, email=email, booking_id=booking_id, amount=total,
                payment_method=data.payment_method, account_number=data.account_number,
                card_last4=data.card_last4, card_expiry=data.card_expiry, cvv=data.cvv,
            )

    return {"status":"success","booking_id":booking_id,"pnr":pnr,"total":total}

@app.get("/get-all-bookings")
async def get_all_bookings():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM bookings WHERE status!='CANCELLED' ORDER BY booking_date DESC")
    return [dict(r) for r in rows]

@app.put("/update-booking/{booking_id}")
async def update_booking(booking_id: str, data: BookingData):
    d     = _validate_future_date(data.travel_date)
    train = _get_train(data.train_id)
    async with db_pool.acquire() as conn:
        old = await conn.fetchrow("SELECT * FROM bookings WHERE booking_id=$1", booking_id)
        if not old:
            raise HTTPException(404, "Booking not found.")
        old       = dict(old)
        new_coach = data.seat_label.split("-")[0]

        # ── Seat conflict check (only if seat/date/train changed) ──
        if any([data.seat_label != old["seat_label"], str(d) != str(old["travel_date"]), data.train_id != old["train_id"]]):
            if await conn.fetchrow(
                "SELECT id FROM seat_availability WHERE train_id=$1 AND travel_date=$2 AND coach=$3 AND seat_number=$4 AND is_booked=TRUE",
                data.train_id, d, new_coach, data.seat_label
            ):
                raise HTTPException(409, "Selected seat is already booked.")

        fare         = _calc_fare(data.selected_class, train["price_factor"], data.passenger_type)
        total        = fare + RABTA_CHARGE
        user_source  = data.user_source.strip()      or train["source"]
        user_dest    = data.user_destination.strip()  or train["destination"]
        ticket_route = f"{user_source} → {user_dest}"
        train_route  = f"{train['source']} → {train['destination']}"
        email        = data.email_id or old["email_id"]

        async with conn.transaction():
            await _upsert_user(conn, email=email, full_name=data.full_name or data.passenger_name, phone=data.passenger_phone)
            await conn.execute(
                "UPDATE seat_availability SET is_booked=FALSE,booked_by_email=NULL,booked_at=NULL WHERE train_id=$1 AND travel_date=$2 AND coach=$3 AND seat_number=$4",
                old["train_id"],old["travel_date"],old["coach"],old["seat_label"]
            )
            await conn.execute(
                """INSERT INTO seat_availability
                     (train_id,travel_date,selected_class,coach,seat_number,is_booked,booked_by_email,booked_at)
                   VALUES ($1,$2,$3,$4,$5,TRUE,$6,NOW())
                   ON CONFLICT (train_id,travel_date,coach,seat_number)
                   DO UPDATE SET is_booked=TRUE,booked_by_email=EXCLUDED.booked_by_email,booked_at=NOW()""",
                data.train_id,d,data.selected_class,new_coach,data.seat_label,email,
            )
            await conn.execute(
                """UPDATE bookings SET
                     train_id=$1,train_name=$2,train_route=$3,travel_date=$4,train_time=$5,
                     passenger_name=$6,passenger_cnic=$7,passenger_phone=$8,passenger_type=$9,
                     user_source=$10,user_destination=$11,ticket_route=$12,
                     selected_class=$13,coach=$14,seat_label=$15,fare=$16,rabta_charge=$17,total=$18,
                     status='MODIFIED',updated_at=NOW()
                   WHERE booking_id=$19""",
                data.train_id,train["name"],train_route,d,train["time"],
                data.passenger_name,data.passenger_cnic,data.passenger_phone,data.passenger_type,
                user_source,user_dest,ticket_route,
                data.selected_class,new_coach,data.seat_label,fare,RABTA_CHARGE,total,booking_id,
            )
            await _insert_payment(conn, email=email, booking_id=booking_id, amount=total,
                                   payment_method=data.payment_method, account_number=data.account_number,
                                   card_last4=data.card_last4, card_expiry=data.card_expiry, cvv=data.cvv)
    return {"msg":"Ticket updated successfully.","total":total}

@app.delete("/delete-booking/{booking_id}")
async def delete_booking(booking_id: str):
    try:
        async with db_pool.acquire() as conn:
            b = await conn.fetchrow("SELECT * FROM bookings WHERE booking_id=$1 AND status='CONFIRMED'", booking_id)
            if not b:
                raise HTTPException(404, "Booking not found or already cancelled")
            b               = dict(b)
            total_amount    = float(b["total"])
            refunded_amount = round(total_amount * REFUND_PERCENT, 2)
            async with conn.transaction():
                await conn.execute(
                    "UPDATE seat_availability SET is_booked=FALSE,booked_by_email=NULL,booked_at=NULL WHERE train_id=$1 AND travel_date=$2 AND coach=$3 AND seat_number=$4",
                    b["train_id"],b["travel_date"],b["coach"],b["seat_label"]
                )
                await conn.execute(
                    "INSERT INTO cancellations (email_id,booking_id,pnr,total_amount,reason) VALUES ($1,$2,$3,$4,'User requested cancellation')",
                    b["email_id"],b["booking_id"],b["pnr"],total_amount
                )
                await conn.execute("DELETE FROM bookings WHERE booking_id=$1", booking_id)
        return {"msg":"Ticket cancelled successfully.","total_paid":total_amount,"refunded_amount":refunded_amount,"refund_percent":"85%"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Cancellation failed: {str(e)}")