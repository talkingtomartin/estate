import base64
import calendar
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from app import models
from app.config import OPENAI_API_KEY
from app.database import get_db
from app.security import get_current_user, flash, get_flashes
from app.storage import save_file
from app.templates_config import templates

router = APIRouter(tags=["transactions"])

INCOME_CATEGORIES = [
    "Husleie",
    "Depositum",
    "Parkeringsinntekt",
    "Andre inntekter",
]

EXPENSE_CATEGORIES = [
    "Forsikring",
    "Vedlikehold og reparasjoner",
    "Kommunale avgifter",
    "Strøm og energi",
    "Internett og TV",
    "Renter",
    "Avdrag",
    "Eiendomsskatt",
    "Fellesutgifter",
    "Regnskapsfører",
    "Andre utgifter",
]


# ── Receipt AI parsing (OpenAI GPT-4o vision) ────────────────────────────────

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

@router.post("/transactions/parse-receipt")
async def parse_receipt(
    request: Request,
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "AI ikke konfigurert"}, status_code=503)

    media_type = file.content_type or ""
    if media_type not in SUPPORTED_IMAGE_TYPES:
        return JSONResponse({"error": "Kun bildefiler støttes (JPEG, PNG, WEBP)"}, status_code=400)

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        return JSONResponse({"error": "Filen er for stor (maks 5 MB)"}, status_code=400)

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        b64 = base64.standard_b64encode(data).decode("utf-8")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{b64}",
                            "detail": "low",
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "This is a receipt. Extract and return ONLY valid JSON, no extra text:\n"
                            '{"amount": <final total as number, no currency>, '
                            '"date": "<YYYY-MM-DD>", '
                            '"description": "<merchant name or brief item description, max 50 chars>"}\n'
                            "Use null for any value you cannot find. "
                            "Parse Norwegian date formats if needed."
                        ),
                    },
                ],
            }],
        )

        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        return JSONResponse(result)

    except (json.JSONDecodeError, IndexError):
        return JSONResponse({"error": "Kunne ikke lese kvitteringen"}, status_code=422)
    except Exception:
        return JSONResponse({"error": "Noe gikk galt"}, status_code=500)


def _save_attachment(file: UploadFile) -> tuple[str, str] | tuple[None, None]:
    path = save_file(file, "transactions")
    if not path:
        return None, None
    return path, file.filename


def _get_property(db: Session, property_id: int, user_id: int) -> models.Property | None:
    """Return property if user is owner or account-level collaborator."""
    from app.routers.properties import _can_access_property
    return _can_access_property(db, property_id, user_id)


# ── All transactions overview ────────────────────────────────────────────────

PERIODS = {
    "last_month": "Forrige måned",
    "this_month":  "Denne måneden",
    "last_30":    "Siste 30 dager",
    "last_90":    "Siste 90 dager",
    "ytd":        "År til dato",
    "this_year":  "I år",
}


def _period_range(period: str, from_date: str | None, to_date: str | None) -> tuple[date, date]:
    today = date.today()
    if period == "custom" and from_date and to_date:
        return date.fromisoformat(from_date), date.fromisoformat(to_date)
    if period == "this_month":
        return date(today.year, today.month, 1), today
    if period == "last_30":
        return today - timedelta(days=29), today
    if period == "last_90":
        return today - timedelta(days=89), today
    if period in ("ytd", "this_year"):
        return date(today.year, 1, 1), today
    # default: last_month
    first_of_this = date(today.year, today.month, 1)
    last_day_prev = first_of_this - timedelta(days=1)
    return date(last_day_prev.year, last_day_prev.month, 1), last_day_prev


@router.get("/transactions/all")
async def all_transactions(
    request: Request,
    period: str = "last_month",
    from_date: str = None,
    to_date: str = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    from app.routers.properties import _accessible_owner_ids
    owner_ids = _accessible_owner_ids(db, user.id)

    start, end = _period_range(period, from_date, to_date)

    transactions = (
        db.query(models.Transaction)
        .join(models.Property)
        .filter(
            models.Property.user_id.in_(owner_ids),
            or_(
                and_(
                    models.Transaction.is_recurring == False,
                    models.Transaction.date >= start,
                    models.Transaction.date <= end,
                ),
                and_(
                    models.Transaction.is_recurring == True,
                    models.Transaction.date <= end,
                ),
            ),
        )
        .order_by(models.Transaction.date.desc(), models.Transaction.id.desc())
        .all()
    )

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expenses = sum(t.amount for t in transactions if t.type == "expense")

    return templates.TemplateResponse(request, "transactions/all.html", {
        "user": user,
        "transactions": transactions,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net": total_income - total_expenses,
        "period": period,
        "from_date": from_date or start.isoformat(),
        "to_date": to_date or end.isoformat(),
        "period_start": start,
        "period_end": end,
        "periods": PERIODS,
        "flash_messages": get_flashes(request),
    })


# ── Quick expense / income (property chosen in form) ────────────────────────

@router.get("/transactions/new")
async def quick_transaction_page(
    request: Request,
    type: str = "expense",
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    from app.routers.properties import _accessible_owner_ids
    owner_ids = _accessible_owner_ids(db, user.id)
    properties = (
        db.query(models.Property)
        .filter(models.Property.user_id.in_(owner_ids))
        .order_by(models.Property.name)
        .all()
    )
    return templates.TemplateResponse(request, "transactions/quick.html", {
        "user": user,
        "properties": properties,
        "default_type": type,
        "today": date.today().isoformat(),
        "income_categories": INCOME_CATEGORIES,
        "expense_categories": EXPENSE_CATEGORIES,
        "flash_messages": get_flashes(request),
    })


@router.post("/transactions/new")
async def quick_create_transaction(
    request: Request,
    property_id: int = Form(...),
    type: str = Form(...),
    description: str = Form(...),
    amount: float = Form(...),
    transaction_date: str = Form(...),
    category: str = Form(""),
    is_recurring: str = Form("off"),
    notes: str = Form(""),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prop = _get_property(db, property_id, user.id)
    if not prop:
        flash(request, "Eiendommen ble ikke funnet.", "error")
        return RedirectResponse(url="/transactions/new", status_code=302)

    txn = models.Transaction(
        property_id=property_id,
        type=type,
        description=description.strip(),
        amount=abs(amount),
        date=date.fromisoformat(transaction_date),
        category=category or None,
        is_recurring=(is_recurring == "on"),
        notes=notes.strip() or None,
    )
    db.add(txn)
    db.flush()

    file_path, filename = _save_attachment(attachment)
    if file_path:
        db.add(models.Attachment(transaction_id=txn.id, file_path=file_path, filename=filename))

    db.commit()
    txn_date = date.fromisoformat(transaction_date)
    flash(request, "Transaksjon lagt til.", "success")
    return RedirectResponse(
        url=f"/properties/{property_id}?year={txn_date.year}&month={txn_date.month}",
        status_code=302,
    )


# ── New transaction ──────────────────────────────────────────────────────────

@router.get("/properties/{property_id}/transactions/new")
async def new_transaction_page(
    property_id: int,
    request: Request,
    type: str = "expense",
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prop = _get_property(db, property_id, user.id)
    if not prop:
        return RedirectResponse(url="/properties", status_code=302)

    return templates.TemplateResponse(request, "transactions/new.html", {
        "user": user,
        "prop": prop,
        "default_type": type,
        "today": date.today().isoformat(),
        "income_categories": INCOME_CATEGORIES,
        "expense_categories": EXPENSE_CATEGORIES,
        "flash_messages": get_flashes(request),
    })


@router.post("/properties/{property_id}/transactions/new")
async def create_transaction(
    property_id: int,
    request: Request,
    type: str = Form(...),
    description: str = Form(...),
    amount: float = Form(...),
    transaction_date: str = Form(...),
    category: str = Form(""),
    is_recurring: str = Form("off"),
    notes: str = Form(""),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prop = _get_property(db, property_id, user.id)
    if not prop:
        return RedirectResponse(url="/properties", status_code=302)

    txn = models.Transaction(
        property_id=property_id,
        type=type,
        description=description.strip(),
        amount=abs(amount),
        date=date.fromisoformat(transaction_date),
        category=category or None,
        is_recurring=(is_recurring == "on"),
        notes=notes.strip() or None,
    )
    db.add(txn)
    db.flush()

    file_path, filename = _save_attachment(attachment)
    if file_path:
        att = models.Attachment(
            transaction_id=txn.id,
            file_path=file_path,
            filename=filename,
        )
        db.add(att)

    db.commit()

    txn_date = date.fromisoformat(transaction_date)
    flash(request, "Transaksjon lagt til.", "success")
    return RedirectResponse(
        url=f"/properties/{property_id}?year={txn_date.year}&month={txn_date.month}",
        status_code=302,
    )


# ── Edit transaction ─────────────────────────────────────────────────────────

@router.get("/transactions/{transaction_id}/edit")
async def edit_transaction_page(
    transaction_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    txn = _get_transaction(db, transaction_id, user.id)
    if not txn:
        return RedirectResponse(url="/properties", status_code=302)

    return templates.TemplateResponse(request, "transactions/edit.html", {
        "user": user,
        "txn": txn,
        "prop": txn.property,
        "income_categories": INCOME_CATEGORIES,
        "expense_categories": EXPENSE_CATEGORIES,
        "flash_messages": get_flashes(request),
    })


@router.post("/transactions/{transaction_id}/edit")
async def update_transaction(
    transaction_id: int,
    request: Request,
    type: str = Form(...),
    description: str = Form(...),
    amount: float = Form(...),
    transaction_date: str = Form(...),
    category: str = Form(""),
    is_recurring: str = Form("off"),
    notes: str = Form(""),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    txn = _get_transaction(db, transaction_id, user.id)
    if not txn:
        return RedirectResponse(url="/properties", status_code=302)

    txn.type = type
    txn.description = description.strip()
    txn.amount = abs(amount)
    txn.date = date.fromisoformat(transaction_date)
    txn.category = category or None
    txn.is_recurring = (is_recurring == "on")
    txn.notes = notes.strip() or None

    file_path, filename = _save_attachment(attachment)
    if file_path:
        att = models.Attachment(
            transaction_id=txn.id,
            file_path=file_path,
            filename=filename,
        )
        db.add(att)

    db.commit()
    flash(request, "Transaksjon oppdatert.", "success")
    return RedirectResponse(
        url=f"/properties/{txn.property_id}?year={txn.date.year}&month={txn.date.month}",
        status_code=302,
    )


# ── Delete attachment ────────────────────────────────────────────────────────

@router.post("/attachments/{attachment_id}/delete")
async def delete_attachment(
    attachment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    att = (
        db.query(models.Attachment)
        .join(models.Transaction)
        .join(models.Property)
        .filter(
            models.Attachment.id == attachment_id,
            models.Property.user_id == user.id,
        )
        .first()
    )
    if att:
        txn_id = att.transaction_id
        txn = db.query(models.Transaction).get(txn_id)
        db.delete(att)
        db.commit()
        flash(request, "Vedlegg slettet.", "success")
        return RedirectResponse(url=f"/transactions/{txn_id}/edit", status_code=302)
    return RedirectResponse(url="/properties", status_code=302)


# ── Delete transaction ───────────────────────────────────────────────────────

@router.post("/transactions/{transaction_id}/delete")
async def delete_transaction(
    transaction_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    txn = _get_transaction(db, transaction_id, user.id)
    if txn:
        property_id = txn.property_id
        year, month = txn.date.year, txn.date.month
        db.delete(txn)
        db.commit()
        flash(request, "Transaksjon slettet.", "success")
        return RedirectResponse(
            url=f"/properties/{property_id}?year={year}&month={month}",
            status_code=302,
        )
    return RedirectResponse(url="/properties", status_code=302)


def _get_transaction(db: Session, transaction_id: int, user_id: int) -> models.Transaction | None:
    return (
        db.query(models.Transaction)
        .join(models.Property)
        .filter(
            models.Transaction.id == transaction_id,
            models.Property.user_id == user_id,
        )
        .first()
    )
