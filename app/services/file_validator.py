from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings


ALLOWED_EXTENSIONS = {".kml", ".zip"}


async def validate_upload(file: UploadFile) -> bytes:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only .kml files or .zip Shapefile archives are supported.")

    data = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, f"File exceeds the {settings.max_upload_size_mb} MB upload limit.")
    if not data:
        raise HTTPException(400, "Uploaded file is empty.")
    return data
