from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import COOKIE_NAME, read_token


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    uid = read_token(token) if token else None
    user = db.get(User, uid) if uid else None
    if user is None:
        raise HTTPException(401, "Войдите в аккаунт")
    if user.is_blocked:
        raise HTTPException(403, "Аккаунт заблокирован. Напишите в поддержку.")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Только для администратора")
    return user
