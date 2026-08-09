"""Panel image uploads.

The interesting cases are all about *not trusting the client*: the declared content type,
the filename and the extension are all attacker-controlled, so validation is done on the
bytes themselves.
"""

from app.api.uploads import MAX_IMAGE_BYTES
from tests.conftest import make_company

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64
WEBP = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 64


async def _upload(client, owner, content: bytes, filename="pic.png", content_type="image/png"):
    return await client.post(
        "/api/v1/uploads/image",
        files={"file": (filename, content, content_type)},
        headers=owner["headers"],
    )


async def test_png_upload_returns_a_url(client):
    owner = await make_company(client)
    resp = await _upload(client, owner, PNG)
    assert resp.status_code == 201
    body = resp.json()
    assert body["url"].startswith("http")
    assert body["content_type"] == "image/png"
    assert body["size"] == len(PNG)


async def test_all_supported_formats_are_accepted(client):
    owner = await make_company(client)
    for content, expected in [
        (PNG, "image/png"),
        (JPEG, "image/jpeg"),
        (GIF, "image/gif"),
        (WEBP, "image/webp"),
    ]:
        resp = await _upload(client, owner, content)
        assert resp.status_code == 201, resp.text
        assert resp.json()["content_type"] == expected


async def test_svg_is_rejected_even_when_declared_as_png(client):
    """SVG is XML that can carry script — serving it from our origin would be stored XSS."""
    owner = await make_company(client)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    resp = await _upload(client, owner, svg, filename="logo.png", content_type="image/png")
    assert resp.status_code == 422
    assert "Unsupported image format" in resp.json()["detail"]


async def test_html_disguised_as_an_image_is_rejected(client):
    owner = await make_company(client)
    html = b"<!DOCTYPE html><script>fetch('/api/v1/company')</script>"
    resp = await _upload(client, owner, html, filename="x.jpg", content_type="image/jpeg")
    assert resp.status_code == 422


async def test_the_declared_content_type_is_not_trusted(client):
    """A real PNG mislabelled as a PDF still uploads — the bytes are what count."""
    owner = await make_company(client)
    resp = await _upload(client, owner, PNG, filename="x.pdf", content_type="application/pdf")
    assert resp.status_code == 201
    assert resp.json()["content_type"] == "image/png"


async def test_stored_extension_comes_from_the_bytes_not_the_filename(client):
    owner = await make_company(client)
    resp = await _upload(client, owner, JPEG, filename="totally.png")
    assert resp.json()["url"].endswith(".jpg")


async def test_path_traversal_in_the_filename_is_neutralised(client):
    owner = await make_company(client)
    resp = await _upload(client, owner, PNG, filename="../../../../etc/passwd.png")
    assert resp.status_code == 201
    url = resp.json()["url"]
    assert ".." not in url
    assert "etc" not in url.rsplit("/", 1)[-1] or "passwd" in url.rsplit("/", 1)[-1]


async def test_oversized_image_is_rejected(client):
    owner = await make_company(client)
    too_big = PNG + b"\x00" * (MAX_IMAGE_BYTES + 1)
    resp = await _upload(client, owner, too_big)
    assert resp.status_code == 413


async def test_empty_file_is_rejected(client):
    owner = await make_company(client)
    resp = await _upload(client, owner, b"")
    assert resp.status_code == 422


async def test_upload_requires_authentication(client):
    resp = await client.post(
        "/api/v1/uploads/image", files={"file": ("pic.png", PNG, "image/png")}
    )
    assert resp.status_code == 401


async def test_uploads_are_stored_per_company(client):
    """The path is tenant-scoped so a bucket policy can reason about ownership."""
    first = await make_company(client)
    second = await make_company(client, "Other")

    one = (await _upload(client, first, PNG)).json()["url"]
    two = (await _upload(client, second, PNG)).json()["url"]

    assert first["company_id"] in one
    assert second["company_id"] in two
    assert one != two


async def test_uploaded_url_can_be_saved_on_a_record(client):
    """End to end: upload, then attach the URL to a branch."""
    owner = await make_company(client)
    url = (await _upload(client, owner, PNG)).json()["url"]

    created = await client.post(
        "/api/v1/branches",
        json={"name": "Чиланзар", "photo_url": url},
        headers=owner["headers"],
    )
    assert created.status_code == 201
    assert created.json()["photo_url"] == url
