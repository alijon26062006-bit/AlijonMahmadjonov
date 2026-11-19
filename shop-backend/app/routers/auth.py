import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_user
from ..models import User
from ..security import COOKIE_NAME, hash_password, make_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

# simple in-memory limiter: max 5 failed logins per IP+email in 10 minutes
_FAILS: dict[str, deque] = defaultdict(deque)
WINDOW, MAX_FAILS = 600, 5


def _too_many(key: str) -> bool:
    q = _FAILS[key]
    now = time.monotonic()
    while q and now - q[0] > WINDOW:
        q.popleft()
    return len(q) >= MAX_FAILS


class RegisterIn(BaseModel):
    email: EmailStr
    username: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _u(cls, v: str) -> str:
        if not USERNAME_RE.match(v):
            raise ValueError("От 3 до 32 символов: латинские буквы, цифры, точка, дефис, подчёркивание")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    role: str
    balance: str


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, username=u.username, role=u.role, balance=f"{u.balance:.4f}")


def _set_cookie(resp: Response, user_id: int) -> None:
    s = get_settings()
    resp.set_cookie(COOKIE_NAME, make_token(user_id), max_age=s.session_days * 86400, httponly=True,
                    secure=s.cookie_secure, samesite="lax", path="/")


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    exists = db.scalar(select(User).where(or_(func.lower(User.email) == email,
                                               func.lower(User.username) == data.username.lower())))
    if exists:
        raise HTTPException(409, "Эта почта или имя пользователя уже заняты")
    role = "admin" if email in get_settings().admin_email_set else "user"
    user = User(email=email, username=data.username, password_hash=hash_password(data.password), role=role)
    db.add(user)
    db.commit()
    _set_cookie(response, user.id)
    return user_out(user)


@router.post("/login", response_model=UserOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    key = f"{request.client.host if request.client else '-'}|{email}"
    if _too_many(key):
        raise HTTPException(429, "Слишком много попыток. Подождите 10 минут.")
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not user or not verify_password(user.password_hash, data.password):
        _FAILS[key].append(time.monotonic())
        raise HTTPException(401, "Неверная почта или пароль")
    if user.is_blocked:
        raise HTTPException(403, "Аккаунт заблокирован. Напишите в поддержку.")
    _FAILS.pop(key, None)
    _set_cookie(response, user.id)
    return user_out(user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user)
