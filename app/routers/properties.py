import calendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy import extract, or_, and_
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import get_current_user, flash, get_flashes
from app.storage import save_file
from app.templates_config import templates

router = APIRouter(prefix="/properties", tags=["properties"])

MONTHS = [
    "januar", "februar", "mars", "april", "mai", "juni",
    "juli", "august", "september", "oktober", "november", "desember",
]


def _month_name(month: int) -> str:
    return MONTHS[month - 1]


def _get_accessible_property(
    db: Session, property_id: int, user_id: int
) -> tuple[models.Property | None, str | None]:
    """Return (property, role) where role is 'owner' or 'member', or (None, None)."""
    prop = db.query(models.Property).filter(models.Property.id == property_id).first()
    if not prop:
        return None, None
    if prop.user_id == user_id:
        return prop, "owner"
    member = db.query(models.PropertyMember).filter(
        models.PropertyMember.property_id == property_id,
        models.PropertyMember.user_id == user_id,
    ).first()
    if member:
        return prop, "member"
    return None, None


@router.get("")
async def list_properties(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    # Show owned properties + properties shared with user
    owned = (
        db.query(models.Property)
        .filter(models.Property.user_id == user.id)
        .all()
    )
    shared = (
        db.query(models.Property)
        .join(models.PropertyMember, models.PropertyMember.property_id == models.Property.id)
        .filter(models.PropertyMember.user_id == user.id)
        .all()
    )
    # Merge, preserve order: owned first then shared
    seen = {p.id for p in owned}
    properties = owned + [p for p in shared if p.id not in seen]

    return templates.TemplateResponse(request, "properties/index.html", {
        "user": user,
        "properties": properties,
        "shared_ids": {p.id for p in shared},
        "flash_messages": get_flashes(request),
    })


@router.get("/new")
async def new_property_page(
    request: Request,
    user: models.User = Depends(get_current_user),
):
    return templates.TemplateResponse(request, "properties/new.html", {
        "user": user,
        "flash_messages": get_flashes(request),
    })


@router.post("/new")
async def create_property(
    request: Request,
    name: str = Form(...),
    address: str = Form(""),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    image_path = save_file(image, "properties")
    prop = models.Property(
        user_id=user.id,
        name=name.strip(),
        address=address.strip() or None,
        image_path=image_path,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    flash(request, f'Eiendommen "{prop.name}" ble opprettet.', "success")
    return RedirectResponse(url=f"/properties/{prop.id}", status_code=302)


@router.get("/{property_id}")
async def property_detail(
    property_id: int,
    request: Request,
    year: int = None,
    month: int = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prop, role = _get_accessible_property(db, property_id, user.id)
    if not prop:
        flash(request, "Eiendommen ble ikke funnet.", "error")
        return RedirectResponse(url="/properties", status_code=302)

    today = date.today()
    year = year or today.year
    month = month or today.month

    last_day = calendar.monthrange(year, month)[1]
    month_end = date(year, month, last_day)
    month_start = date(year, month, 1)

    transactions = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.property_id == property_id,
            or_(
                and_(
                    models.Transaction.is_recurring == False,
                    extract("year", models.Transaction.date) == year,
                    extract("month", models.Transaction.date) == month,
                ),
                and_(
                    models.Transaction.is_recurring == True,
                    models.Transaction.date <= month_end,
                ),
            ),
        )
        .order_by(models.Transaction.date.desc())
        .all()
    )

    income = [t for t in transactions if t.type == "income"]
    expenses = [t for t in transactions if t.type == "expense"]

    prev_month_date = month_start - timedelta(days=1)
    next_month_date = month_end + timedelta(days=1)

    members = (
        db.query(models.PropertyMember)
        .filter(models.PropertyMember.property_id == property_id)
        .all()
    )

    return templates.TemplateResponse(request, "properties/detail.html", {
        "user": user,
        "prop": prop,
        "role": role,
        "members": members,
        "transactions": transactions,
        "income": income,
        "expenses": expenses,
        "total_income": sum(t.amount for t in income),
        "total_expenses": sum(t.amount for t in expenses),
        "net": sum(t.amount for t in income) - sum(t.amount for t in expenses),
        "year": year,
        "month": month,
        "prev_year": prev_month_date.year,
        "prev_month": prev_month_date.month,
        "next_year": next_month_date.year,
        "next_month": next_month_date.month,
        "month_name": _month_name(month),
        "flash_messages": get_flashes(request),
    })


@router.post("/{property_id}/invite")
async def invite_member(
    property_id: int,
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prop = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.user_id == user.id,
    ).first()
    if not prop:
        flash(request, "Kun eieren kan invitere samarbeidspartnere.", "error")
        return RedirectResponse(url=f"/properties/{property_id}", status_code=302)

    invitee = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not invitee:
        flash(request, f'Ingen bruker med e-post «{email}» er registrert.', "error")
        return RedirectResponse(url=f"/properties/{property_id}", status_code=302)

    if invitee.id == user.id:
        flash(request, "Du kan ikke invitere deg selv.", "error")
        return RedirectResponse(url=f"/properties/{property_id}", status_code=302)

    existing = db.query(models.PropertyMember).filter(
        models.PropertyMember.property_id == property_id,
        models.PropertyMember.user_id == invitee.id,
    ).first()
    if existing:
        flash(request, f'{invitee.name or invitee.email} har allerede tilgang.', "error")
        return RedirectResponse(url=f"/properties/{property_id}", status_code=302)

    db.add(models.PropertyMember(
        property_id=property_id,
        user_id=invitee.id,
        invited_by_id=user.id,
    ))
    db.commit()
    flash(request, f'{invitee.name or invitee.email} ble lagt til som samarbeidspartner.', "success")
    return RedirectResponse(url=f"/properties/{property_id}", status_code=302)


@router.post("/{property_id}/members/{member_id}/remove")
async def remove_member(
    property_id: int,
    member_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prop = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.user_id == user.id,
    ).first()
    if not prop:
        flash(request, "Kun eieren kan fjerne samarbeidspartnere.", "error")
        return RedirectResponse(url=f"/properties/{property_id}", status_code=302)

    member = db.query(models.PropertyMember).filter(
        models.PropertyMember.id == member_id,
        models.PropertyMember.property_id == property_id,
    ).first()
    if member:
        db.delete(member)
        db.commit()
        flash(request, "Samarbeidspartner fjernet.", "success")
    return RedirectResponse(url=f"/properties/{property_id}", status_code=302)


@router.post("/{property_id}/leave")
async def leave_property(
    property_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    member = db.query(models.PropertyMember).filter(
        models.PropertyMember.property_id == property_id,
        models.PropertyMember.user_id == user.id,
    ).first()
    if member:
        db.delete(member)
        db.commit()
        flash(request, "Du har forlatt eiendommen.", "success")
    return RedirectResponse(url="/properties", status_code=302)


@router.post("/{property_id}/delete")
async def delete_property(
    property_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prop = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.user_id == user.id,
    ).first()
    if prop:
        db.delete(prop)
        db.commit()
        flash(request, f'Eiendommen "{prop.name}" ble slettet.', "success")
    return RedirectResponse(url="/properties", status_code=302)
