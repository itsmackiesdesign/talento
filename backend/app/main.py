"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import (
    admin,
    application_statuses,
    applications,
    billing,
    bots,
    branches,
    companies,
    dashboard,
    news,
    notifications,
    questions,
    uploads,
    vacancies,
    webhook,
)
from app.api import auth as auth_api
from app.core.config import settings
from app.core.logging import RequestIdMiddleware, configure_logging, get_logger
from app.core.redis_client import close_redis
from app.services.storage import s3_enabled

configure_logging()
log = get_logger(__name__)

if settings.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENV, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the Dispatcher up front so the first webhook doesn't pay for handler registration.
    from app.bot.runtime import get_dispatcher

    get_dispatcher()
    log.info("api_started", env=settings.ENV, base_url=settings.BASE_URL)
    yield
    await close_redis()


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Talento API",
    description="HR platform for Telegram vacancy bots",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Too many requests, slow down"})


api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth_api.router)
api_v1.include_router(admin.router)
api_v1.include_router(billing.router)
api_v1.include_router(companies.router)
api_v1.include_router(bots.router)
api_v1.include_router(branches.router)
api_v1.include_router(vacancies.router)
api_v1.include_router(questions.router)
api_v1.include_router(news.router)
api_v1.include_router(uploads.router)
api_v1.include_router(applications.router)
api_v1.include_router(application_statuses.router)
api_v1.include_router(dashboard.router)
api_v1.include_router(notifications.router)

app.include_router(api_v1)
app.include_router(webhook.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "env": settings.ENV, "version": app.version}


# Local-disk fallback for candidate files; production serves these from S3 instead.
if not s3_enabled():
    upload_dir = Path(settings.LOCAL_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(upload_dir)), name="files")


# When a frontend build is present, expose it from the API process as a same-origin SPA.
# This gives local Telegram notifications a real public HTTPS panel URL through the same
# ngrok tunnel already required for webhooks, without needing a second tunnel.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(frontend_dist / "assets")),
        name="frontend-assets",
    )

    @app.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(frontend_dist / "index.html")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def frontend_spa(frontend_path: str) -> FileResponse:
        # Reserved backend paths must keep returning an API 404, not index.html.
        if frontend_path.startswith(("api/", "webhook/", "files/")):
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        requested = (frontend_dist / frontend_path).resolve()
        if requested.is_relative_to(frontend_dist) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(frontend_dist / "index.html")
