from datetime import datetime, timedelta
import bcrypt
from jose import JWTError, jwt
from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_DAYS
from app.database import get_db
from app import models


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> models.User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Ikke innlogget")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Ugyldig token")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Bruker ikke funnet")
    return user


def flash(request: Request, message: str, category: str = "info") -> None:
    msgs = request.session.get("flash", [])
    msgs.append({"message": message, "category": category})
    request.session["flash"] = msgs


def get_flashes(request: Request) -> list:
    msgs = request.session.get("flash", [])
    request.session["flash"] = []
    return msgs
