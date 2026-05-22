from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator, model_validator
import re
import random
import hashlib
from datetime import date, datetime, timedelta
import asyncpg
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from typing import Optional, Literal

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

db_pool: asyncpg.Pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=5,
        statement_cache_size=0,
        ssl="require",
    )
    yield
    if db_pool:
        await db_pool.close()


app = FastAPI(title="Pakistan Railway Ticketing API", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


STATIONS = [
    "Karachi City",
    "Karachi Cantonment",
    "Hyderabad",
    "Nawabshah",
    "Sukkur",
    "Bahawalpur",
    "Khanewal",
    "Sahiwal",
    "Multan Cantonment",
    "Faisalabad",
    "Lahore",
    "Gujranwala",
    "Sialkot",
    "Sargodha",
    "Rawalpindi",
    "Margala",
    "Peshawar Cantonment",
    "Peshawar City",
    "Quetta",
]

TRAINS = [
    {
        "id": 1, "name": "5UP - Green Line Express", "time": "22:00",
        "source": "Karachi Cantonment", "destination": "Margala",
        "stops": ["Karachi Cantonment", "Hyderabad", "Rohri", "Bahawalpur",
                  "Khanewal", "Lahore", "Rawalpindi", "Margala"],
        "price_factor": 1.2,
    },
    {
        "id": 2, "name": "41UP - Karakoram Express", "time": "15:30",
        "source": "Karachi Cantonment", "destination": "Lahore",
        "stops": ["Karachi Cantonment", "Hyderabad", "Nawabshah",
                  "Sukkur", "Bahawalpur", "Khanewal", "Sahiwal", "Lahore"],
        "price_factor": 1.0,
    },
    {
        "id": 3, "name": "33UP - Pak Business Express", "time": "16:00",
        "source": "Karachi Cantonment", "destination": "Lahore",
        "stops": ["Karachi Cantonment", "Hyderabad",
                  "Sukkur", "Multan Cantonment", "Faisalabad", "Lahore"],
        "price_factor": 1.1,
    },
    {
        "id": 4, "name": "17UP - Millat Express", "time": "14:15",
        "source": "Karachi Cantonment", "destination": "Sargodha",
        "stops": ["Karachi Cantonment", "Hyderabad", "Nawabshah",
                  "Sukkur", "Multan Cantonment", "Khanewal", "Faisalabad", "Sargodha"],
        "price_factor": 0.9,
    },
    {
        "id": 5, "name": "9UP - Allama Iqbal Express", "time": "14:00",
        "source": "Karachi Cantonment", "destination": "Sialkot",
        "stops": ["Karachi Cantonment", "Hyderabad",
                  "Sukkur", "Bahawalpur", "Lahore", "Gujranwala", "Sialkot"],
        "price_factor": 0.85,
    },
    {
        "id": 6, "name": "1UP - Khyber Mail", "time": "22:15",
        "source": "Karachi Cantonment", "destination": "Peshawar City",
        "stops": ["Karachi Cantonment", "Hyderabad", "Nawabshah",
                  "Sukkur", "Multan Cantonment", "Lahore", "Rawalpindi", "Margala",
                  "Peshawar Cantonment", "Peshawar City"],
        "price_factor": 0.95,
    },
    {
        "id": 7, "name": "6DN - Green Line Express", "time": "20:00",
        "source": "Margala", "destination": "Karachi Cantonment",
        "stops": ["Margala", "Rawalpindi", "Lahore", "Khanewal",
                  "Bahawalpur", "Rohri", "Hyderabad", "Karachi Cantonment"],
        "price_factor": 1.2,
    },
    {
        "id": 8, "name": "42DN - Karakoram Express", "time": "15:00",
        "source": "Lahore", "destination": "Karachi Cantonment",
        "stops": ["Lahore", "Sahiwal", "Khanewal", "Bahawalpur",
                  "Sukkur", "Nawabshah", "Hyderabad", "Karachi Cantonment"],
        "price_factor": 1.0,
    },
    {
        "id": 9, "name": "34DN - Pak Business Express", "time": "16:30",
        "source": "Lahore", "destination": "Karachi Cantonment",
        "stops": ["Lahore", "Faisalabad", "Multan Cantonment",
                  "Sukkur", "Hyderabad", "Karachi Cantonment"],
        "price_factor": 1.1,
    },
    {
        "id": 10, "name": "18DN - Millat Express", "time": "13:30",
        "source": "Sargodha", "destination": "Karachi Cantonment",
        "stops": ["Sargodha", "Faisalabad", "Khanewal", "Multan Cantonment",
                  "Sukkur", "Nawabshah", "Hyderabad", "Karachi Cantonment"],
        "price_factor": 0.9,
    },
    {
        "id": 11, "name": "10DN - Allama Iqbal Express", "time": "12:00",
        "source": "Sialkot", "destination": "Karachi Cantonment",
        "stops": ["Sialkot", "Gujranwala", "Lahore", "Bahawalpur",
                  "Sukkur", "Hyderabad", "Karachi Cantonment"],
        "price_factor": 0.85,
    },
    {
        "id": 12, "name": "2DN - Khyber Mail", "time": "06:00",
        "source": "Peshawar City", "destination": "Karachi Cantonment",
        "stops": ["Peshawar City", "Peshawar Cantonment", "Margala", "Rawalpindi",
                  "Lahore", "Multan Cantonment", "Sukkur", "Nawabshah",
                  "Hyderabad", "Karachi Cantonment"],
        "price_factor": 0.95,
    },
    {
        "id": 13, "name": "21UP - Lahore Express", "time": "08:00",
        "source": "Rawalpindi", "destination": "Lahore",
        "stops": ["Rawalpindi", "Margala", "Gujranwala", "Lahore"],
        "price_factor": 0.9,
    },
    {
        "id": 14, "name": "22DN - Lahore Express", "time": "18:00",
        "source": "Lahore", "destination": "Rawalpindi",
        "stops": ["Lahore", "Gujranwala", "Margala", "Rawalpindi"],
        "price_factor": 0.9,
    },
    {
        "id": 15, "name": "7UP - Awam Express", "time": "10:00",
        "source": "Karachi Cantonment", "destination": "Quetta",
        "stops": ["Karachi Cantonment", "Hyderabad",
                  "Nawabshah", "Sukkur", "Quetta"],
        "price_factor": 0.8,
    },
    {
        "id": 16, "name": "8DN - Awam Express", "time": "09:00",
        "source": "Quetta", "destination": "Karachi Cantonment",
        "stops": ["Quetta", "Sukkur", "Nawabshah",
                  "Hyderabad", "Karachi Cantonment"],
        "price_factor": 0.8,
    },
    {
        "id": 17, "name": "11UP - Peshawar Express", "time": "07:30",
        "source": "Rawalpindi", "destination": "Peshawar City",
        "stops": ["Rawalpindi", "Margala", "Peshawar Cantonment", "Peshawar City"],
        "price_factor": 0.85,
    },
    {
        "id": 18, "name": "12DN - Peshawar Express", "time": "17:00",
        "source": "Peshawar City", "destination": "Rawalpindi",
        "stops": ["Peshawar City", "Peshawar Cantonment", "Margala", "Rawalpindi"],
        "price_factor": 0.85,
    },
    {
        "id": 19, "name": "23UP - Chenab Express", "time": "09:00",
        "source": "Faisalabad", "destination": "Lahore",
        "stops": ["Faisalabad", "Sahiwal", "Lahore"],
        "price_factor": 0.8,
    },
    {
        "id": 20, "name": "24DN - Chenab Express", "time": "19:00",
        "source": "Lahore", "destination": "Faisalabad",
        "stops": ["Lahore", "Sahiwal", "Faisalabad"],
        "price_factor": 0.8,
    },
]

CLASS_CONFIG = {
    "AC Business": {
        "coaches": ["A1", "A2"],
        "cabins_per_coach": 4,
        "berths_per_cabin": 6,
        "berth_labels": ["1-Lower", "2-Middle", "3-Upper", "4-Lower", "5-Middle", "6-Upper"],
    },
    "AC Standard": {
        "coaches": ["B1", "B2", "B3"],
        "cabins_per_coach": 6,
        "berths_per_cabin": 6,
        "berth_labels": ["1-Lower", "2-Middle", "3-Upper", "4-Lower", "5-Middle", "6-Upper"],
    },
    "Economy": {
        "coaches": ["C1", "C2", "C3", "C4"],
        "cabins_per_coach": 8,
        "berths_per_cabin": 6,
        "berth_labels": ["1-Lower", "2-Middle", "3-Upper", "4-Lower", "5-Middle", "6-Upper"],
    },
}

BASE_CLASS_PRICES = {
    "AC Business": 13250,
    "AC Standard": 6500,
    "Economy":     3500,
}

RABTA_CHARGE   = 10
REFUND_PERCENT = 0.85

PAYMENT_METHODS = Literal["JazzCash", "Easypaisa", "MasterCard", "Visa"]

PAYMENT_PIN_RULES = {
    "JazzCash":   {"account_digits": 11, "pin_digits": 4,  "label": "JazzCash Account (11 digits)"},
    "Easypaisa":  {"account_digits": 11, "pin_digits": 6,  "label": "Easypaisa Account (11 digits)"},
    "MasterCard": {"account_digits": 4,  "pin_digits": 4,  "label": "MasterCard Last 4 Digits", "cvv": 4},
    "Visa":       {"account_digits": 4,  "pin_digits": 4,  "label": "Visa Card Last 4 Digits",  "cvv": 4},
}


def _get_booking_window() -> tuple[date, date]:
    today_date = date.today()
    month = today_date.month + 2
    year  = today_date.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    day = min(today_date.day, last_day)
    max_date = date(year, month, day)
    return today_date, max_date


EXCLUSIVE_ROUTES: dict[tuple[str, str], set[int]] = {
    ("karachi cantonment", "margala"): {1},
    ("margala", "karachi cantonment"): {7},
}

def _is_route_exclusive(source_lower: str, dest_lower: str, train_id: int) -> bool:
    key = (source_lower, dest_lower)
    if key in EXCLUSIVE_ROUTES:
        return train_id not in EXCLUSIVE_ROUTES[key]
    return False


def _is_train_available(train_id: int, travel_date: date) -> bool:
    if train_id in [1, 7]:
        return True

    days_ahead = (travel_date - date.today()).days
    seed_str = f"train_avail_{train_id}_{travel_date.isoformat()}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 10000

    if days_ahead <= 7:
        threshold = 9500
    elif days_ahead <= 21:
        threshold = 8000
    elif days_ahead <= 35:
        threshold = 6500
    else:
        threshold = 5000

    return (seed % 10000) < threshold


async def _get_booked_seat_keys_db(train_id: int, travel_date: date, selected_class: str) -> set:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT seat_number FROM seat_availability
            WHERE train_id = $1
              AND travel_date = $2
              AND selected_class = $3
              AND is_booked = TRUE
            """,
            train_id, travel_date, selected_class
        )
    return {row["seat_number"] for row in rows}


def _get_seat_availability_layout(
    train_id: int,
    travel_date: date,
    selected_class: str,
    booked_from_db: set
) -> list:
    config = CLASS_CONFIG.get(selected_class)
    if not config:
        return []

    seats = []
    date_str = travel_date.isoformat()

    for coach in config["coaches"]:
        for cabin_num in range(1, config["cabins_per_coach"] + 1):
            cabin_seats = []
            for berth_idx, berth_label in enumerate(config["berth_labels"]):
                seat_label = f"{coach}-Cabin{cabin_num}-{berth_label}"

                if seat_label in booked_from_db:
                    available = False
                else:
                    seed_str = f"seat_avail_{train_id}_{date_str}_{seat_label}"
                    seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 100
                    available = seed < 65

                cabin_seats.append({
                    "label":     seat_label,
                    "coach":     coach,
                    "cabin":     cabin_num,
                    "berth":     berth_label,
                    "available": available,
                })
            seats.append({
                "coach":  coach,
                "cabin":  cabin_num,
                "berths": cabin_seats,
            })

    return seats


class BookingData(BaseModel):
    passenger_name:  str
    passenger_cnic:  str
    passenger_phone: str
    passenger_type:  str

    train_id:         int
    travel_date:      str
    selected_class:   str
    seat_label:       str

    payment_method:   str = "Visa"
    account_number:   str = ""
    payment_pin:      str = ""
    cvv:              str = ""
    card_digits:      str = ""

    user_source:      str = ""
    user_destination: str = ""
    email_id:         str = ""
    full_name:        str = ""

    @field_validator("passenger_name")
    @classmethod
    def validate_passenger_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Passenger name is required.")
        if not re.fullmatch(r"[A-Za-z ]{2,60}", v):
            raise ValueError(
                "Passenger name must contain only English alphabets and spaces "
                "(2–60 characters). No numbers or special characters allowed."
            )
        return v

    @field_validator("passenger_cnic")
    @classmethod
    def validate_passenger_cnic(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"\d{5}-\d{7}-\d", v):
            raise ValueError(
                "CNIC must be in the format XXXXX-XXXXXXX-X "
                "(13 digits with 2 dashes, e.g. 42101-1234567-8)."
            )
        return v

    @field_validator("passenger_phone")
    @classmethod
    def validate_passenger_phone(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"0\d{3}-\d{7}", v):
            raise ValueError(
                "Phone number must be in Pakistani format: 0XXX-XXXXXXX "
                "(12 characters including dash, starting with 0, e.g. 0321-1234567)."
            )
        return v

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        allowed = {"JazzCash", "Easypaisa", "MasterCard", "Visa"}
        if v not in allowed:
            raise ValueError(f"Payment method must be one of: {', '.join(sorted(allowed))}.")
        return v

    @model_validator(mode="after")
    def validate_payment_fields(self) -> "BookingData":
        method = self.payment_method
        acct   = self.account_number.strip()
        pin    = self.payment_pin.strip()
        cvv    = self.cvv.strip()

        if method in ("JazzCash", "Easypaisa"):
            if not re.fullmatch(r"03\d{9}", acct):
                raise ValueError(
                    f"{method} account number must be 11 digits starting with 03 "
                    f"(e.g. 03XXXXXXXXX)."
                )
            expected_pin = 4 if method == "JazzCash" else 6
            if not re.fullmatch(r"\d{" + str(expected_pin) + r"}", pin):
                raise ValueError(
                    f"{method} PIN must be exactly {expected_pin} digits."
                )

        elif method in ("MasterCard", "Visa"):
            if not re.fullmatch(r"\d{4}", acct):
                raise ValueError(
                    f"{method} requires the last 4 digits of your card number."
                )
            if not re.fullmatch(r"\d{4}", cvv):
                raise ValueError(
                    f"{method} CVV must be exactly 4 digits."
                )
            if not re.fullmatch(r"\d{4}", pin):
                raise ValueError(
                    f"{method} PIN must be exactly 4 digits."
                )
            self.card_digits = acct

        return self


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
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
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("Please provide a valid email address.")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[A-Za-z ]{2,60}", v):
            raise ValueError(
                "Full name must contain only English alphabets and spaces (2–60 characters)."
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        errors = []
        if len(v) < 8:
            errors.append("at least 8 characters")
        if not re.search(r"[A-Z]", v):
            errors.append("one uppercase letter")
        if not re.search(r"[0-9]", v):
            errors.append("one number")
        if not re.search(r"[!@#$%^&*()\-_=+\[\]{};':\"\\|,.<>/?`~]", v):
            errors.append("one special character")
        if errors:
            raise ValueError("Password must contain: " + ", ".join(errors) + ".")
        return v


def _validate_future_date(travel_date: str) -> date:
    try:
        d = datetime.strptime(travel_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    today_date, max_date = _get_booking_window()

    if d < today_date:
        raise HTTPException(status_code=400, detail="Travel date cannot be in the past.")

    if d > max_date:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Bookings are only available up to 2 months in advance. "
                f"Maximum booking date is {max_date.strftime('%d %b %Y')}. "
                f"Please check back later for dates beyond this window."
            )
        )
    return d


def _get_train(train_id: int) -> dict:
    t = next((t for t in TRAINS if t["id"] == train_id), None)
    if not t:
        raise HTTPException(status_code=404, detail="Train not found.")
    return t


def _calc_fare(selected_class: str, price_factor: float, passenger_type: str) -> int:
    base = BASE_CLASS_PRICES.get(selected_class, 0)
    fare = base * price_factor
    if passenger_type == "Child":
        fare /= 2
    return round(fare)


def _calc_refund(total: float) -> float:
    return round(total * REFUND_PERCENT, 2)


async def _upsert_user(conn, email: str, full_name: str, phone: str):
    await conn.execute(
        """
        INSERT INTO users (email, full_name, phone)
        VALUES ($1, $2, $3)
        ON CONFLICT (email) DO UPDATE SET
            full_name  = CASE WHEN EXCLUDED.full_name  != '' THEN EXCLUDED.full_name  ELSE users.full_name  END,
            phone      = CASE WHEN EXCLUDED.phone      != '' THEN EXCLUDED.phone      ELSE users.phone      END,
            updated_at = NOW()
        """,
        email,
        full_name or "",
        phone or "",
    )


async def _insert_payment(
    conn,
    email: str,
    booking_id: str,
    amount: float,
    payment_method: str,
    account_number: str,
    cvv: str = "",
):
    transaction_id = f"TXN-{random.randint(10000000, 99999999)}"

    # ── Method-specific field mapping ──────────────────────────────
    # JazzCash / Easypaisa  → mobile_number stored, card fields NULL
    # Visa / MasterCard     → card_last4 + hashed CVV stored, mobile NULL
    if payment_method in ("JazzCash", "Easypaisa"):
        mobile_number = account_number          # 11-digit mobile
        card_last4    = None
        card_cvv_hash = None
    else:
        mobile_number = None
        card_last4    = account_number[-4:]     # last 4 digits of card
        card_cvv_hash = hashlib.sha256(cvv.encode()).hexdigest() if cvv else None

    await conn.execute(
        """
        INSERT INTO payment_records (
            email_id, booking_id, amount,
            payment_method, transaction_id,
            mobile_number, card_last4, card_cvv_hash,
            status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'SUCCESS')
        """,
        email, booking_id, amount,
        payment_method, transaction_id,
        mobile_number, card_last4, card_cvv_hash,
    )


@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/get-stations")
def get_stations():
    return {"stations": sorted(STATIONS)}


@app.get("/get-booking-window")
def get_booking_window():
    today_date, max_date = _get_booking_window()
    return {
        "today":            today_date.isoformat(),
        "max_date":         max_date.isoformat(),
        "max_date_display": max_date.strftime("%d %b %Y"),
    }


@app.get("/get-payment-methods")
def get_payment_methods():
    return {
        "methods": [
            {
                "id":              "JazzCash",
                "label":           "JazzCash",
                "account_label":   "JazzCash Mobile Number (11 digits)",
                "account_digits":  11,
                "pin_label":       "JazzCash MPIN (4 digits)",
                "pin_digits":      4,
                "requires_cvv":    False,
                "placeholder_acct":"03XXXXXXXXX",
                "placeholder_pin": "XXXX",
            },
            {
                "id":              "Easypaisa",
                "label":           "Easypaisa",
                "account_label":   "Easypaisa Mobile Number (11 digits)",
                "account_digits":  11,
                "pin_label":       "Easypaisa MPIN (6 digits)",
                "pin_digits":      6,
                "requires_cvv":    False,
                "placeholder_acct":"03XXXXXXXXX",
                "placeholder_pin": "XXXXXX",
            },
            {
                "id":              "MasterCard",
                "label":           "Master Card",
                "account_label":   "Last 4 Digits of Card",
                "account_digits":  4,
                "pin_label":       "Card PIN (4 digits)",
                "pin_digits":      4,
                "requires_cvv":    True,
                "cvv_digits":      4,
                "placeholder_acct":"XXXX",
                "placeholder_pin": "XXXX",
                "placeholder_cvv": "XXXX",
            },
            {
                "id":              "Visa",
                "label":           "Visa Card",
                "account_label":   "Last 4 Digits of Card",
                "account_digits":  4,
                "pin_label":       "Card PIN (4 digits)",
                "pin_digits":      4,
                "requires_cvv":    True,
                "cvv_digits":      4,
                "placeholder_acct":"XXXX",
                "placeholder_pin": "XXXX",
                "placeholder_cvv": "XXXX",
            },
        ]
    }


@app.get("/search-trains")
def search_trains(
    source:      str = Query(...),
    destination: str = Query(...),
    travel_date: str = Query(...),
):
    d = _validate_future_date(travel_date)

    s_lower = [s.lower() for s in STATIONS]
    if source.lower() not in s_lower:
        raise HTTPException(status_code=404, detail=f"Station '{source}' not found.")
    if destination.lower() not in s_lower:
        raise HTTPException(status_code=404, detail=f"Station '{destination}' not found.")
    if source.lower() == destination.lower():
        raise HTTPException(status_code=400, detail="Source and destination cannot be the same.")

    matched = []
    for train in TRAINS:
        if _is_route_exclusive(source.lower(), destination.lower(), train["id"]):
            continue
        if not _is_train_available(train["id"], d):
            continue

        stops_lower = [s.lower() for s in train["stops"]]
        if source.lower() in stops_lower and destination.lower() in stops_lower:
            si = stops_lower.index(source.lower())
            di = stops_lower.index(destination.lower())
            if si < di:
                days_ahead = (d - date.today()).days
                if days_ahead <= 7:
                    avail_label = "Available"
                elif days_ahead <= 21:
                    avail_label = "Limited Seats"
                else:
                    avail_label = "Booking Open"

                matched.append({
                    "id":           train["id"],
                    "name":         train["name"],
                    "time":         train["time"],
                    "source":       train["stops"][si],
                    "destination":  train["stops"][di],
                    "price_factor": train["price_factor"],
                    "avail_label":  avail_label,
                    "days_ahead":   days_ahead,
                })

    return {"trains": matched, "travel_date": travel_date, "count": len(matched)}


@app.get("/get-seats")
async def get_seats(train_id: int, selected_class: str, travel_date: str):
    d = _validate_future_date(travel_date)
    _get_train(train_id)

    config = CLASS_CONFIG.get(selected_class)
    if not config:
        raise HTTPException(status_code=400, detail="Invalid class.")

    booked_from_db = await _get_booked_seat_keys_db(train_id, d, selected_class)
    cabin_layout   = _get_seat_availability_layout(train_id, d, selected_class, booked_from_db)
    return {
        "cabins": cabin_layout,
        "class":  selected_class,
        "config": {
            "coaches":          config["coaches"],
            "cabins_per_coach": config["cabins_per_coach"],
            "berths_per_cabin": config["berths_per_cabin"],
        }
    }


@app.post("/confirm-booking")
async def confirm_booking(data: BookingData):
    d     = _validate_future_date(data.travel_date)
    train = _get_train(data.train_id)

    if not _is_train_available(data.train_id, d):
        raise HTTPException(status_code=400, detail="This train is not available on the selected date.")

    fare  = _calc_fare(data.selected_class, train["price_factor"], data.passenger_type)
    total = fare + RABTA_CHARGE

    parts = data.seat_label.split("-")
    coach = parts[0] if parts else "N/A"

    pnr        = f"PR-{random.randint(100000, 999999)}"
    booking_id = f"BK-{random.randint(1000000, 9999999)}"

    user_source  = data.user_source.strip()      if data.user_source      else train["source"]
    user_dest    = data.user_destination.strip()  if data.user_destination else train["destination"]
    ticket_route = f"{user_source} → {user_dest}"
    train_route  = f"{train['source']} → {train['destination']}"
    email        = data.email_id or "guest@railway.pk"

    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id FROM seat_availability
            WHERE train_id = $1 AND travel_date = $2
              AND coach = $3 AND seat_number = $4 AND is_booked = TRUE
            """,
            data.train_id, d, coach, data.seat_label
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="This seat has already been booked. Please select another seat."
            )

        async with conn.transaction():
            await _upsert_user(
                conn,
                email=email,
                full_name=data.full_name or data.passenger_name,
                phone=data.passenger_phone,
            )

            await conn.execute(
                """
                INSERT INTO bookings (
                    booking_id, pnr,
                    train_id, train_name, train_route, travel_date, train_time,
                    passenger_name, passenger_cnic, passenger_phone, passenger_type,
                    user_source, user_destination, ticket_route,
                    selected_class, coach, seat_label,
                    fare, rabta_charge, total,
                    email_id, status
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7,
                    $8, $9, $10, $11,
                    $12, $13, $14,
                    $15, $16, $17,
                    $18, $19, $20,
                    $21, 'CONFIRMED'
                )
                """,
                booking_id, pnr,
                data.train_id, train["name"], train_route, d, train["time"],
                data.passenger_name, data.passenger_cnic, data.passenger_phone, data.passenger_type,
                user_source, user_dest, ticket_route,
                data.selected_class, coach, data.seat_label,
                fare, RABTA_CHARGE, total,
                email,
            )

            await conn.execute(
                """
                INSERT INTO seat_availability (
                    train_id, travel_date, selected_class,
                    coach, seat_number, is_booked, booked_by_email, booked_at
                ) VALUES ($1, $2, $3, $4, $5, TRUE, $6, NOW())
                ON CONFLICT (train_id, travel_date, coach, seat_number)
                DO UPDATE SET
                    is_booked       = TRUE,
                    booked_by_email = EXCLUDED.booked_by_email,
                    booked_at       = NOW()
                """,
                data.train_id, d, data.selected_class,
                coach, data.seat_label, email,
            )

            await _insert_payment(
                conn,
                email=email,
                booking_id=booking_id,
                amount=total,
                payment_method=data.payment_method,
                account_number=data.account_number,
                cvv=data.cvv,
            )

    return {"status": "success", "booking_id": booking_id, "pnr": pnr, "total": total}


@app.get("/get-all-bookings")
async def get_all_bookings():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM bookings WHERE status != 'CANCELLED' ORDER BY booking_date DESC"
        )
    return [dict(r) for r in rows]


@app.put("/update-booking/{booking_id}")
async def update_booking(booking_id: str, data: BookingData):
    d     = _validate_future_date(data.travel_date)
    train = _get_train(data.train_id)

    async with db_pool.acquire() as conn:
        old = await conn.fetchrow(
            "SELECT * FROM bookings WHERE booking_id = $1", booking_id
        )
        if not old:
            raise HTTPException(status_code=404, detail="Booking not found.")

        old = dict(old)

        parts     = data.seat_label.split("-")
        new_coach = parts[0] if parts else "N/A"

        if (data.seat_label != old["seat_label"]
                or str(d) != str(old["travel_date"])
                or data.train_id != old["train_id"]):
            conflict = await conn.fetchrow(
                """
                SELECT id FROM seat_availability
                WHERE train_id = $1 AND travel_date = $2
                  AND coach = $3 AND seat_number = $4 AND is_booked = TRUE
                """,
                data.train_id, d, new_coach, data.seat_label
            )
            if conflict:
                raise HTTPException(status_code=409, detail="Selected seat is already booked.")

        fare  = _calc_fare(data.selected_class, train["price_factor"], data.passenger_type)
        total = fare + RABTA_CHARGE

        user_source  = data.user_source.strip()     if data.user_source      else train["source"]
        user_dest    = data.user_destination.strip() if data.user_destination else train["destination"]
        ticket_route = f"{user_source} → {user_dest}"
        train_route  = f"{train['source']} → {train['destination']}"
        email        = data.email_id or old["email_id"]

        async with conn.transaction():
            await _upsert_user(
                conn,
                email=email,
                full_name=data.full_name or data.passenger_name,
                phone=data.passenger_phone,
            )

            await conn.execute(
                """
                UPDATE seat_availability
                SET is_booked = FALSE, booked_by_email = NULL, booked_at = NULL
                WHERE train_id = $1 AND travel_date = $2
                  AND coach = $3 AND seat_number = $4
                """,
                old["train_id"], old["travel_date"], old["coach"], old["seat_label"]
            )

            await conn.execute(
                """
                INSERT INTO seat_availability (
                    train_id, travel_date, selected_class,
                    coach, seat_number, is_booked, booked_by_email, booked_at
                ) VALUES ($1, $2, $3, $4, $5, TRUE, $6, NOW())
                ON CONFLICT (train_id, travel_date, coach, seat_number)
                DO UPDATE SET
                    is_booked       = TRUE,
                    booked_by_email = EXCLUDED.booked_by_email,
                    booked_at       = NOW()
                """,
                data.train_id, d, data.selected_class,
                new_coach, data.seat_label, email,
            )

            await conn.execute(
                """
                UPDATE bookings SET
                    train_id         = $1,  train_name       = $2,
                    train_route      = $3,  travel_date      = $4,
                    train_time       = $5,  passenger_name   = $6,
                    passenger_cnic   = $7,  passenger_phone  = $8,
                    passenger_type   = $9,  user_source      = $10,
                    user_destination = $11, ticket_route     = $12,
                    selected_class   = $13, coach            = $14,
                    seat_label       = $15, fare             = $16,
                    rabta_charge     = $17, total            = $18,
                    status           = 'MODIFIED', updated_at = NOW()
                WHERE booking_id = $19
                """,
                data.train_id, train["name"], train_route, d, train["time"],
                data.passenger_name, data.passenger_cnic, data.passenger_phone, data.passenger_type,
                user_source, user_dest, ticket_route,
                data.selected_class, new_coach, data.seat_label,
                fare, RABTA_CHARGE, total,
                booking_id,
            )

            await _insert_payment(
                conn,
                email=email,
                booking_id=booking_id,
                amount=total,
                payment_method=data.payment_method,
                account_number=data.account_number,
                cvv=data.cvv,
            )

    return {"msg": "Ticket updated successfully.", "total": total}


@app.delete("/delete-booking/{booking_id}")
async def delete_booking(booking_id: str):
    try:
        async with db_pool.acquire() as conn:
            b = await conn.fetchrow(
                "SELECT * FROM bookings WHERE booking_id = $1 AND status = 'CONFIRMED'",
                booking_id
            )
            if not b:
                raise HTTPException(status_code=404, detail="Booking not found or already cancelled.")

            b = dict(b)
            total_amount    = float(b["total"])
            refunded_amount = _calc_refund(total_amount)

            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE seat_availability
                    SET is_booked = FALSE,
                        booked_by_email = NULL,
                        booked_at = NULL
                    WHERE train_id = $1
                      AND travel_date = $2
                      AND coach = $3
                      AND seat_number = $4
                    """,
                    b["train_id"], b["travel_date"], b["coach"], b["seat_label"]
                )

                await conn.execute(
                    """
                    INSERT INTO cancellations (
                        email_id, booking_id, pnr,
                        total_amount, reason
                    ) VALUES ($1, $2, $3, $4, 'User requested cancellation')
                    """,
                    b["email_id"], b["booking_id"], b["pnr"], total_amount
                )

                await conn.execute(
                    "DELETE FROM bookings WHERE booking_id = $1",
                    booking_id
                )

            return {
                "msg":             "Ticket cancelled successfully. Record moved to cancellations.",
                "total_paid":      total_amount,
                "refunded_amount": refunded_amount,
                "refund_percent":  "85%",
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cancellation failed: {str(e)}")