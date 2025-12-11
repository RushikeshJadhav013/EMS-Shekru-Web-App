from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings
from app.utils.timezone import now_ist

def create_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = now_ist() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt
