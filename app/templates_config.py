import os
from fastapi.templating import Jinja2Templates
from app.storage import media_url

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))
templates.env.cache = None
templates.env.filters["media_url"] = media_url
