"""Structured logging (structlog) + request-id middleware."""

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def _add_request_id(_logger, _name, event_dict):
    event_dict["request_id"] = request_id_ctx.get()
    return event_dict


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s", stream=sys.stdout, level=getattr(logging, settings.LOG_LEVEL, 20)
    )
    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.ENV == "dev"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _add_request_id,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL, 20)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "talento"):
    return structlog.get_logger(name)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_ctx.reset(token)
