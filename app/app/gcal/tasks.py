import logging

from huey import crontab

from django.core.cache import cache
from django.utils import timezone

from constance import config
from huey.contrib import djhuey

from carb import constants
from common.tasks import once_at_startup

from .models import GoogleCalendarShowTimes


logger = logging.getLogger(f'carb.{__name__}')


@djhuey.db_periodic_task(once_at_startup(crontab(minute='*/5')))
@djhuey.lock_task('sync-google-calendar-api-lock')
def sync_google_calendar_api():
    if config.GOOGLE_CALENDAR_ENABLED:
        logger.info('Synchronizing with Google Calendar API')
        try:
            GoogleCalendarShowTimes.sync_api()
        except Exception:
            cache.set(constants.CACHE_KEY_GCAL_LAST_SYNC,
                      "Failed, please check your settings and try again.", timeout=None)
            raise
        else:
            cache.set(constants.CACHE_KEY_GCAL_LAST_SYNC, timezone.now(), timeout=None)
    else:
        logger.info('Synchronization with Google Calendar API disabled by config')
