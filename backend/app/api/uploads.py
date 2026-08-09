"""Panel image uploads — logos, branch and vacancy photos, news pictures."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.deps import CurrentCompany
from app.core.logging import get_logger
from app.services.storage import save_company_image, sniff_image

router = APIRouter(prefix="/uploads", tags=["uploads"])
log = get_logger(__name__)

# Panel images are illustrations, not documents — a few megabytes is plenty, and a small
# ceiling keeps a single request from pinning memory while the body is buffered.
MAX_IMAGE_BYTES = 5 * 1024 * 1024


@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_image(
    company: CurrentCompany,
    file: Annotated[UploadFile, File()],
) -> dict:
    """Store an image and return its URL for the caller to save on a record.

    The upload is validated by *sniffing the bytes*, never by the declared content type or
    the file extension — both are attacker-controlled. Anything that is not a recognised
    raster image is rejected, which in particular keeps SVG out: it is XML that can carry
    script, and serving it back from our own origin would be stored XSS.
    """
    content = await file.read()

    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The file is empty")

    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Image is too large. Maximum {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
        )

    sniffed = sniff_image(content)
    if sniffed is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Unsupported image format. Use JPEG, PNG, WebP or GIF.",
        )
    content_type, _ = sniffed

    url = await save_company_image(
        company.id, content, file.filename or "image", content_type
    )
    log.info(
        "image_uploaded",
        company_id=str(company.id),
        bytes=len(content),
        content_type=content_type,
    )
    return {"url": url, "content_type": content_type, "size": len(content)}
