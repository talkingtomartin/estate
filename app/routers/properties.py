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


def _accessible_owner_ids(db: Session, user_id: int) -> list[int]:
    """Return list of owner IDs whose properties the current user can access (includes self)."""
    collab_owner_ids = [
        row.owner_id for row in
        db.query(models.Collaborator.owner_id)
        .filter(models.Collaborator.user_id == user_id)
        .all()
    ]
    return [user_id] + collab_owner_ids


def _can_access_property(db: Session, property_id: int, user_id: int) -> models.Property | None:
    owner_ids = _accessible_owner_ids(db, user_id)
    return db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.user_id.in_(owner_ids),
    ).first()


@router.get("")
async def list_properties(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    owner_ids = _accessible_owner_ids(db, user.id)
    properties = (
        db.query(models.Property)
        .filter(models.Property.user_id.in_(owner_ids))
        .order_by(models.Property.user_id != user.id, models.Property.created_at.desc())
        .all()
    )

    recent_transactions = (
        db.query(models.Transaction)
        .join(models.Property)
        .filter(models.Property.user_id.in_(owner_ids))
        .order_by(models.Transaction.date.desc(), models.Transaction.id.desc())
        .limit(10)
        .all()
    )

    return templates.TemplateResponse(request, "properties/index.html", {
        "user": user,
        "properties": properties,
        "recent_transactions": recent_transactions,
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
    purchase_price: str = Form(""),
    current_value: str = Form(""),
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
        purchase_price=float(purchase_price) if purchase_price.strip() else None,
        current_value=float(current_value) if current_value.strip() else None,
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
    prop = _can_access_property(db, property_id, user.id)
    if not prop:
        flash(request, "Eiendommen ble ikke funnet.", "error")
        return RedirectResponse(url="/properties", status_code=302)

    is_owner = prop.user_id == user.id

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

    return templates.TemplateResponse(request, "properties/detail.html", {
        "user": user,
        "prop": prop,
        "is_owner": is_owner,
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


@router.post("/{property_id}/investments")
async def add_investment(
    property_id: int,
    request: Request,
    description: str = Form(...),
    amount: float = Form(...),
    investment_date: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prop = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.user_id == user.id,
    ).first()
    if prop:
        from datetime import date as date_type
        inv = models.PropertyInvestment(
            property_id=property_id,
            description=description.strip(),
            amount=abs(amount),
            date=date_type.fromisoformat(investment_date) if investment_date.strip() else None,
        )
        db.add(inv)
        db.commit()
        flash(request, "Investering lagt til.", "success")
    return RedirectResponse(url=f"/properties/{property_id}", status_code=302)


@router.post("/{property_id}/investments/{investment_id}/delete")
async def delete_investment(
    property_id: int,
    investment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    inv = (
        db.query(models.PropertyInvestment)
        .join(models.Property)
        .filter(
            models.PropertyInvestment.id == investment_id,
            models.Property.id == property_id,
            models.Property.user_id == user.id,
        )
        .first()
    )
    if inv:
        db.delete(inv)
        db.commit()
        flash(request, "Investering fjernet.", "success")
    return RedirectResponse(url=f"/properties/{property_id}", status_code=302)


@router.post("/{property_id}/valuation")
async def update_valuation(
    property_id: int,
    request: Request,
    purchase_price: str = Form(""),
    current_value: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prop = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.user_id == user.id,
    ).first()
    if prop:
        prop.purchase_price = float(purchase_price) if purchase_price.strip() else None
        prop.current_value = float(current_value) if current_value.strip() else None
        db.commit()
        flash(request, "Verdier oppdatert.", "success")
    return RedirectResponse(url=f"/properties/{property_id}", status_code=302)


# ── Account-level collaboration ──────────────────────────────────────────────

@router.post("/team/invite")
async def invite_collaborator(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    invitee = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not invitee:
        flash(request, f'Ingen bruker med e-post «{email}» er registrert.', "error")
        return RedirectResponse(url="/profile", status_code=302)

    if invitee.id == user.id:
        flash(request, "Du kan ikke invitere deg selv.", "error")
        return RedirectResponse(url="/profile", status_code=302)

    existing = db.query(models.Collaborator).filter(
        models.Collaborator.owner_id == user.id,
        models.Collaborator.user_id == invitee.id,
    ).first()
    if existing:
        flash(request, f'{invitee.name or invitee.email} har allerede tilgang.', "error")
        return RedirectResponse(url="/profile", status_code=302)

    db.add(models.Collaborator(owner_id=user.id, user_id=invitee.id))
    db.commit()
    flash(request, f'{invitee.name or invitee.email} kan nå se alle dine eiendommer.', "success")
    return RedirectResponse(url="/profile", status_code=302)


@router.post("/team/{collaborator_id}/remove")
async def remove_collaborator(
    collaborator_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    collab = db.query(models.Collaborator).filter(
        models.Collaborator.id == collaborator_id,
        models.Collaborator.owner_id == user.id,
    ).first()
    if collab:
        db.delete(collab)
        db.commit()
        flash(request, "Tilgang fjernet.", "success")
    return RedirectResponse(url="/profile", status_code=302)


@router.post("/team/{collaborator_id}/leave")
async def leave_team(
    collaborator_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    collab = db.query(models.Collaborator).filter(
        models.Collaborator.id == collaborator_id,
        models.Collaborator.user_id == user.id,
    ).first()
    if collab:
        db.delete(collab)
        db.commit()
        flash(request, "Du har forlatt kontoen.", "success")
    return RedirectResponse(url="/profile", status_code=302)
