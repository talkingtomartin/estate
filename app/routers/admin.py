from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.security import get_current_user
from app.templates_config import templates
from app import models

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users")
async def admin_users(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.email != "talkingtomartin@hotmail.com":
        raise HTTPException(status_code=403, detail="Tilgang nektet")
    
    users = db.query(models.User).all()
    return templates.TemplateResponse(request, "admin/users.html", {
        "users": users,
        "current_user": current_user
    })