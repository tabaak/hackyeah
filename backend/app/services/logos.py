"""Private company logos, isolated by organization and served through signed URLs."""
import logging
import warnings
from io import BytesIO
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from storage3.exceptions import StorageApiError

from app.db import get_db

BUCKET = "company-logos"
MAX_BYTES = 2 * 1024 * 1024
URL_TTL = 24 * 60 * 60
logger = logging.getLogger(__name__)


def path(row: dict) -> str:
    return f"{row['organization_id']}/{row['id']}/logo.webp"


def normalize(data: bytes) -> bytes:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Logo must be smaller than 2 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=["PNG", "JPEG", "WEBP"]) as source:
                if source.width * source.height > 16_000_000 or max(source.size) > 8192:
                    raise HTTPException(413, "Logo dimensions are too large")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
                image.thumbnail((512, 512))
                output = BytesIO()
                image.save(output, format="WEBP", quality=90)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(415, "Choose a valid PNG, JPG or WebP image") from None


def signed_urls(rows: list[dict]) -> dict[str, str]:
    if not rows:
        return {}
    by_path = {path(row): row["id"] for row in rows}
    try:
        urls = get_db().storage.from_(BUCKET).create_signed_urls(list(by_path), URL_TTL)
    except StorageApiError:
        # Logo availability must not prevent the rest of the workspace from loading.
        logger.warning("Company logos are temporarily unavailable")
        return {}
    return {
        by_path[item["path"]]: f"{item['signedURL']}&v={uuid4().hex}"
        for item in urls if not item.get("error") and item.get("signedURL") and item.get("path") in by_path
    }


def upload(row: dict, data: bytes) -> str:
    image = normalize(data)
    get_db().storage.from_(BUCKET).upload(path(row), image, {
        "content-type": "image/webp", "cache-control": "0", "upsert": "true",
    })
    url = signed_urls([row]).get(row["id"])
    if not url:
        raise HTTPException(503, "The logo was saved but could not be loaded. Please try again.")
    return url


def remove(row: dict) -> None:
    try:
        get_db().storage.from_(BUCKET).remove([path(row)])
    except StorageApiError as error:
        if str(error.status) != "404":
            raise
