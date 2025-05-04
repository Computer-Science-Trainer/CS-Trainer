import os
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from fastapi.security.http import HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from fastapi.security import HTTPBearer
from fastapi import Depends, HTTPException
from services.user_service import get_user_by_email
from models.schemas import UserOut
from config import ADMIN_EMAILS

bearer_scheme = HTTPBearer()

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    # Убедитесь, что data["sub"] содержит строку email
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if not isinstance(payload.get("sub"), str):
            raise HTTPException(status_code=401, detail="Invalid token format")
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    payload = decode_access_token(token)
    email = payload.get("sub")

    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    if not isinstance(email, str):
        raise HTTPException(status_code=401, detail="Email must be a string")

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserOut(
        id=user["id"],
        email=user["email"],
        username=user["username"]
    )


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("sub"):  # Проверяем наличие обязательного поля
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    payload = decode_access_token(credentials.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload
