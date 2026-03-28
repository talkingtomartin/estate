import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY, UPLOAD_DIR
from app.routers import auth, properties, transactions

app = FastAPI(title="EstateExpenses")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400 * 30)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


app.include_router(auth.router)
app.include_router(properties.router)
app.include_router(transactions.router)


@app.on_event("startup")
async def startup_event():
    os.makedirs(os.path.join(UPLOAD_DIR, "properties"), exist_ok=True)
    os.makedirs(os.path.join(UPLOAD_DIR, "transactions"), exist_ok=True)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
    )


@app.get("/")
async def root():
    return RedirectResponse(url="/properties", status_code=302)
