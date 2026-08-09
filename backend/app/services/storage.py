"""File storage — S3/MinIO when configured, local disk otherwise.

Two kinds of file live here: candidate uploads coming through the bot, and panel images
(logos, branch and vacancy photos, news pictures). They are kept under separate prefixes so
a bucket policy can treat them differently — panel images are meant to be publicly
readable, candidate résumés are not.

The local fallback exists so the whole product runs on a laptop with nothing but Postgres
and Redis; production should always set the S3_* variables.
"""

import asyncio
import os
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def s3_enabled() -> bool:
    return bool(settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY and settings.S3_BUCKET)


def _safe_name(filename: str) -> str:
    """Never trust a candidate-supplied filename with a path in it."""
    base = os.path.basename(filename or "file")
    base = "".join(ch for ch in base if ch.isalnum() or ch in "._- ").strip() or "file"
    return base[:80]


def _put_to_s3(key: str, content: bytes, content_type: str) -> str:
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )
    client.put_object(
        Bucket=settings.S3_BUCKET, Key=key, Body=content, ContentType=content_type
    )
    if settings.S3_PUBLIC_URL:
        return f"{settings.S3_PUBLIC_URL.rstrip('/')}/{key}"
    if settings.S3_ENDPOINT_URL:
        return f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET}/{key}"
    return f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{key}"


# Magic-byte signatures. The browser-supplied Content-Type is attacker-controlled, so the
# real format is sniffed from the bytes instead — otherwise an HTML or SVG payload could be
# uploaded as "image/png" and served back from our own origin as stored XSS.
_IMAGE_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"GIF87a", "image/gif", ".gif"),
    (b"GIF89a", "image/gif", ".gif"),
)


def sniff_image(content: bytes) -> tuple[str, str] | None:
    """Return ``(content_type, extension)`` for a recognised raster image, else None.

    SVG is deliberately absent: it is XML that can carry script, and serving it from our own
    origin would be an XSS vector no matter what the extension says.
    """
    for signature, content_type, extension in _IMAGE_SIGNATURES:
        if content.startswith(signature):
            return content_type, extension
    # WebP is RIFF-framed: "RIFF" + 4 size bytes + "WEBP".
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


async def save_company_image(
    company_id: uuid.UUID | str, content: bytes, filename: str, content_type: str
) -> str:
    """Store a panel-uploaded image and return a URL the bot and panel can both use."""
    stem = Path(_safe_name(filename)).stem or "image"
    _, extension = sniff_image(content) or ("", ".bin")
    key = f"images/{company_id}/{uuid.uuid4().hex}-{stem}{extension}"

    if s3_enabled():
        return await asyncio.to_thread(_put_to_s3, key, content, content_type)

    dest = Path(settings.LOCAL_UPLOAD_DIR) / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(dest.write_bytes, content)
    log.info("image_saved_locally", path=str(dest), bytes=len(content))
    return f"{settings.BASE_URL.rstrip('/')}/files/{key}"


async def save_candidate_file(
    company_id: uuid.UUID | str,
    content: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Store a résumé/photo and return a URL the panel can link to."""
    key = f"candidates/{company_id}/{uuid.uuid4().hex}-{_safe_name(filename)}"

    if s3_enabled():
        # boto3 is blocking; keep it off the event loop so the webhook stays under 3s.
        return await asyncio.to_thread(_put_to_s3, key, content, content_type)

    dest = Path(settings.LOCAL_UPLOAD_DIR) / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(dest.write_bytes, content)
    log.info("file_saved_locally", path=str(dest), bytes=len(content))
    return f"{settings.BASE_URL.rstrip('/')}/files/{key}"
