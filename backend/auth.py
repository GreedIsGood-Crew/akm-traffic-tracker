# app_pages/auth.py
import os
import logging

from fastapi import APIRouter, Request, Response, HTTPException, status, Depends
from pydantic import BaseModel

from sqlalchemy.orm import Session
from jose import jwt, JWTError
from passlib.context import CryptContext
from hashlib import md5
from db import get_db, get_user, SessionLocal
from datetime import datetime, timedelta

from models.user import UserORM

logger = logging.getLogger(__name__)

router = APIRouter()

# Конфигурация JWT — секрет ТОЛЬКО из environment
SECRET_KEY = os.environ.get("TRACKER_JWT_SECRET")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError("TRACKER_JWT_SECRET env var is required (min 32 chars)")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# bcrypt для хеширования паролей (с поддержкой миграции с MD5)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_LEGACY_SALT = "akm_"


def verify_password(plain_password: str, hashed_password: str, db: Session = None, user: UserORM = None) -> bool:
    """Verify password. Supports migration from legacy MD5 to bcrypt."""
    # Try bcrypt first
    if pwd_context.identify(hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    # Fallback: legacy MD5 verification for migration
    legacy_hash = md5((_LEGACY_SALT + plain_password).encode()).hexdigest()
    if hashed_password == legacy_hash:
        # Auto-migrate to bcrypt on successful login
        if db and user:
            user.password_hash = pwd_context.hash(plain_password)
            db.commit()
            logger.info("Migrated user %s from MD5 to bcrypt", user.username)
        return True

    return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# Генерация токена
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Модель для передачи логина и пароля
class LoginRequest(BaseModel):
    username: str
    password: str


# ====== Проверка авторизации ======
def is_authenticated(request: Request) -> any:
    token = request.cookies.get("session_token")
    if not token:
        return False

    try:
        # Декодируем JWT токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if not username:
            return False

        db: Session = SessionLocal()
        user = get_user(db, username)
        db.close()
        if user:
            if not user.active:
                return False
            else:
                # Проверяем, что токен не просрочен
                if datetime.fromtimestamp(payload["exp"]) < datetime.utcnow():
                    return False
                else:
                    if user.username == "tracker_admin":
                        return "admin"
                    else:
                        return "user"
        else:
            return False


    except JWTError:
        return False


# ====== POST /login ======
@router.post("/login")
async def login(request: Request, response: Response, login_data: LoginRequest, db: Session = Depends(get_db)):
    user = get_user(db, login_data.username)
    if not user:
        logger.info("Login failed: user not found: %s", login_data.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(login_data.password, user.password_hash, db=db, user=user):
        logger.info("Login failed: invalid password for user: %s", login_data.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Генерируем токен
    token_data = {"sub": user.username}
    token = create_access_token(data=token_data)

    # Сохраняем токен в куках
    response.set_cookie(key="session_token", value=token, httponly=True)

    logger.info("Login successful: %s", login_data.username)
    return {"message": "Login successful"}


# ====== POST /logout ======
@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="session_token")
    return {"message": "Logged out"}


# ====== GET /status ======
@router.get("/status")
async def auth_status(request: Request):
    token = request.cookies.get("session_token")
    if token == "valid_token":
        return {"authenticated": True}
    return {"authenticated": False}
