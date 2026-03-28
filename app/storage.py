"""
File storage abstraction.
- Cloudinary is used when CLOUDINARY_* env vars are set (production/Vercel).
- Local disk is used otherwise (development).
"""
import os
import uuid

from fastapi import UploadFile

from app.config import (
    CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME,
    UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE,
)

USE_CLOUDINARY = bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)

if USE_CLOUDINARY:
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )


def save_file(file: UploadFile, folder: str) -> str | None:
    """Save an uploaded file. Returns a URL (Cloudinary) or a relative path (local)."""
    if not file or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None
    content = file.file.read()
    if not content or len(content) > MAX_UPLOAD_SIZE:
        return None

    if USE_CLOUDINARY:
        result = cloudinary.uploader.upload(
            content,
            folder=f"estate/{folder}",
            resource_type="auto",
        )
        return result["secure_url"]

    # Local fallback
    filename = f"{uuid.uuid4()}{ext}"
    dest = os.path.join(UPLOAD_DIR, folder, filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(content)
    return f"uploads/{folder}/{filename}"


def media_url(path: str) -> str:
    """Convert a stored path/URL to a displayable URL for templates."""
    if not path:
        return ""
    if path.startswith("http"):
        return path  # already a Cloudinary URL
    return f"/static/{path}"  # local dev path
