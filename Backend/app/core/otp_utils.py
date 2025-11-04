import random
from datetime import datetime, timedelta
from app.core.config import settings

OTP_STORE = {}

def generate_otp(email: str) -> int:
    otp = random.randint(100000, 999999)
    OTP_STORE[email] = {"otp": otp, "expiry": datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)}
    return otp

def verify_otp(email: str, otp: int) -> bool:
    record = OTP_STORE.get(email)
    if not record:
        return False
    if record["otp"] != otp:
        return False
    if datetime.utcnow() > record["expiry"]:
        del OTP_STORE[email]
        return False
    del OTP_STORE[email]
    return True
