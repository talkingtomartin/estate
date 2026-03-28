from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import get_current_user, flash, get_flashes
from app.storage import save_file

router = APIRouter(prefix="/properties", tags=["properties"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def list_properties(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    properties = (
        db.query(models.Property)
        .filter(models.Property.user_id == user.id)
        .order_by(models.Property.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("properties/index.html", {
        "request": request,
        "user": user,
        "properties": properties,
        "flash_messages": get_flashes(request),
    })


@router.get("/new")
async def new_property_page(
    request: Request,
    user: models.User = Depends(get_current_user),
):
    return templates.TemplateResponse("properties/new.html", {
        "request": request,
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
    from datetime import date, timedelta
    from sqlalchemy import extract, or_, and_
    import calendar

    prop = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.user_id == user.id,
    ).first()
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
    total_income = sum(t.amount for t in income)
    total_expenses = sum(t.amount for t in expenses)

    # Build month navigation (prev / next)
    prev_month_date = month_start - timedelta(days=1)
    next_month_date = month_end + timedelta(days=1)

    return templates.TemplateResponse("properties/detail.html", {
        "request": request,
        "user": user,
        "prop": prop,
        "transactions": transactions,
        "income": income,
        "expenses": expenses,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net": total_income - total_expenses,
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


MONTHS = [
    "januar", "februar", "mars", "april", "mai", "juni",
    "juli", "august", "september", "oktober", "november", "desember",
]


def _month_name(month: int) -> str:
    return MONTHS[month - 1]
