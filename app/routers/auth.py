import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from app.templates_config import templates
from sqlalchemy.orm import Session

from app import models
from app.config import BASE_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.database import get_db
from app.security import (
    create_access_token, flash, get_current_user, get_flashes,
    hash_password, verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@router.get("/login")
async def login_page(request: Request):
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/properties", status_code=302)
    return templates.TemplateResponse(request, "auth/login.html", {
        "flash_messages": get_flashes(request),
        "google_enabled": bool(GOOGLE_CLIENT_ID),
    })


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        flash(request, "Feil e-post eller passord.", "error")
        return RedirectResponse(url="/auth/login", status_code=302)

    token = create_access_token(user.id)
    response = RedirectResponse(url="/properties", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=86400 * 30, samesite="lax")
    return response


@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "auth/register.html", {
        "flash_messages": get_flashes(request),
    })


@router.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if len(password) < 8:
        flash(request, "Passordet må være minst 8 tegn.", "error")
        return RedirectResponse(url="/auth/register", status_code=302)

    existing = db.query(models.User).filter(models.User.email == email.lower()).first()
    if existing:
        flash(request, "E-postadressen er allerede registrert.", "error")
        return RedirectResponse(url="/auth/register", status_code=302)

    user = models.User(
        email=email.lower(),
        name=name,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    response = RedirectResponse(url="/properties", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=86400 * 30, samesite="lax")
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ── Google OAuth2 ────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login(request: Request):
    if not GOOGLE_CLIENT_ID:
        flash(request, "Google-innlogging er ikke konfigurert.", "error")
        return RedirectResponse(url="/auth/login", status_code=302)

    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": f"{BASE_URL}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
    }
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db),
):
    if error or not code:
        flash(request, "Google-innlogging ble avbrutt.", "error")
        return RedirectResponse(url="/auth/login", status_code=302)

    if state != request.session.get("oauth_state"):
        flash(request, "Ugyldig forespørsel.", "error")
        return RedirectResponse(url="/auth/login", status_code=302)

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{BASE_URL}/auth/google/callback",
            "grant_type": "authorization_code",
        })
        token_data = token_resp.json()

        if "access_token" not in token_data:
            flash(request, "Kunne ikke hente token fra Google.", "error")
            return RedirectResponse(url="/auth/login", status_code=302)

        info_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        userinfo = info_resp.json()

    google_id = userinfo.get("id")
    email = userinfo.get("email", "").lower()

    user = db.query(models.User).filter(models.User.google_id == google_id).first()
    if not user:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            user.google_id = google_id
        else:
            user = models.User(
                email=email,
                name=userinfo.get("name", email),
                google_id=google_id,
            )
            db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    response = RedirectResponse(url="/properties", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=86400 * 30, samesite="lax")
    return response
