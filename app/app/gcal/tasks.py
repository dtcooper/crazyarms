import logging

from huey import crontab

from django.core.cache import cache
from django.utils import timezone

from constance import config
from huey.contrib import djhuey

from common.tasks import once_at_startup
from crazyarms import constants

from .models import GCalShow

logger = logging.getLogger(f"crazyarms.{__name__}")


@djhuey.db_periodic_task(priority=2, validate_datetime=once_at_startup(crontab(minute="*/5")))
@djhuey.lock_task("sync-google-calendar-api-lock")
def sync_gcal_api():
    if config.GOOGLE_CALENDAR_ENABLED:
        logger.info("Synchronizing with Google Calendar API")
        try:
            GCalShow.sync_api()
        except Exception:
            cache.set(
                constants.CACHE_KEY_GCAL_LAST_SYNC,
                "Failed, please check your settings and try again.",
                timeout=None,
            )
            raise
        else:
            cache.set(constants.CACHE_KEY_GCAL_LAST_SYNC, timezone.now(), timeout=None)
    else:
        logger.info("Synchronization with Google Calendar API disabled by config")
