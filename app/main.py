import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY, UPLOAD_DIR
from app.routers import auth, properties, transactions
from app.storage import media_url

# Absolute path to project root (works both locally and on Vercel)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(title="Yields")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400 * 30)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "app", "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))

# Vercel's bundled Jinja2 has a bug where env.globals (which always contains
# built-ins like range/dict) ends up as a dict inside the cache key tuple,
# making it unhashable. Setting cache=None bypasses the buggy code path entirely.
templates.env.cache = None
templates.env.filters["media_url"] = media_url


app.include_router(auth.router)
app.include_router(properties.router)
app.include_router(transactions.router)


@app.on_event("startup")
async def startup_event():
    # Only create local upload dirs when not using Cloudinary (Vercel filesystem is read-only)
    try:
        os.makedirs(os.path.join(UPLOAD_DIR, "properties"), exist_ok=True)
        os.makedirs(os.path.join(UPLOAD_DIR, "transactions"), exist_ok=True)
    except OSError:
        pass


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
    )


@app.get("/")
async def root():
    return RedirectResponse(url="/properties", status_code=302)
