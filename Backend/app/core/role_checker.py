# from fastapi import Depends, HTTPException, status
# from jose import jwt, JWTError
# from fastapi.security import HTTPBearer
# from app.core.config import settings

# security = HTTPBearer()

# def get_current_user(token: str = Depends(security)):
#     try:
#         payload = jwt.decode(token.credentials, settings.SECRET_KEY, algorithms=["HS256"])
#         email: str = payload.get("sub")
#         role: str = payload.get("role")
#         if email is None or role is None:
#             raise HTTPException(status_code=401, detail="Invalid token")
#         return {"email": email, "role": role}
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Invalid or expired token")


from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from jose import jwt, JWTError
from app.core.config import settings
from app.enums import RoleEnum
from app.dependencies import require_roles

# This will extract token from Authorization header
api_key_header = APIKeyHeader(name="Authorization")

def get_current_user(token: str = Depends(api_key_header)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None or role is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"email": email, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# --- Role Checkers ---
def role_required(*allowed_roles):
    def wrapper(current_user=Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for role: {current_user['role']}"
            )
        return current_user
    return wrapper

_: RoleEnum = Depends(require_roles([RoleEnum.ADMIN, RoleEnum.HR]))
