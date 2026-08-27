"""Celery application. Broker and result backend both live in Redis."""

import logging

from celery import Celery
from celery.signals import after_setup_logger, after_setup_task_logger

from app.core.config import settings

celery_app = Celery(
    "talento",
    broker=settings.celery_broker_url,
    backend=settings.celery_broker_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=4,
    task_time_limit=300,
    task_soft_time_limit=240,
    broker_connection_retry_on_startup=True,
)


def _suppress_credential_bearing_transport_logs(**_kwargs) -> None:
    """httpx INFO messages include the Telegram Bot API URL, which embeds its token."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


after_setup_logger.connect(_suppress_credential_bearing_transport_logs)
after_setup_task_logger.connect(_suppress_credential_bearing_transport_logs)
