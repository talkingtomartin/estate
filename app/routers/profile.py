from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import get_current_user, verify_password, hash_password, flash, get_flashes
from app.templates_config import templates

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def profile_page(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    my_collaborators = (
        db.query(models.Collaborator)
        .filter(models.Collaborator.owner_id == user.id)
        .all()
    )
    my_memberships = (
        db.query(models.Collaborator)
        .filter(models.Collaborator.user_id == user.id)
        .all()
    )
    return templates.TemplateResponse(request, "profile/index.html", {
        "user": user,
        "my_collaborators": my_collaborators,
        "my_memberships": my_memberships,
        "flash_messages": get_flashes(request),
    })


@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if not user.password_hash:
        flash(request, "Passordet kan ikke endres for Google-kontoer.", "error")
        return RedirectResponse(url="/profile", status_code=302)

    if not verify_password(current_password, user.password_hash):
        flash(request, "Nåværende passord er feil.", "error")
        return RedirectResponse(url="/profile", status_code=302)

    if new_password != confirm_password:
        flash(request, "De nye passordene stemmer ikke overens.", "error")
        return RedirectResponse(url="/profile", status_code=302)

    if len(new_password) < 8:
        flash(request, "Nytt passord må være minst 8 tegn.", "error")
        return RedirectResponse(url="/profile", status_code=302)

    user.password_hash = hash_password(new_password)
    db.commit()
    flash(request, "Passordet ble endret.", "success")
    return RedirectResponse(url="/profile", status_code=302)
