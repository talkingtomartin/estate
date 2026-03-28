from datetime import date

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import get_current_user, flash, get_flashes
from app.storage import save_file

router = APIRouter(tags=["transactions"])
templates = Jinja2Templates(directory="app/templates")

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


def _save_attachment(file: UploadFile) -> tuple[str, str] | tuple[None, None]:
    path = save_file(file, "transactions")
    if not path:
        return None, None
    return path, file.filename


def _get_property(db: Session, property_id: int, user_id: int) -> models.Property | None:
    return db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.user_id == user_id,
    ).first()


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

    return templates.TemplateResponse("transactions/new.html", {
        "request": request,
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

    return templates.TemplateResponse("transactions/edit.html", {
        "request": request,
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
