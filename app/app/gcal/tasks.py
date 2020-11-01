import logging

import huey

from django.core.cache import cache
from django.utils import timezone

from constance import config
from huey.contrib import djhuey

from carb import constants

from .models import GoogleCalendarShowTimes


logger = logging.getLogger(f'carb.{__name__}')


def crontab_and_startup(*args, **kwargs):
    needs_to_run = True
    crontab = huey.crontab(*args, **kwargs)

    def startup_crontab(dt):
        nonlocal needs_to_run
        if needs_to_run:
            needs_to_run = False
            return True
        else:
            return crontab(dt)

    return startup_crontab


@djhuey.db_periodic_task(crontab_and_startup(minute='*/15'))
@djhuey.lock_task('sync-google-calendar-api-lock')
def sync_google_calendar_api():
    if config.GOOGLE_CALENDAR_ENABLED:
        logger.info('Synchronizing with Google Calendar API')
        try:
            GoogleCalendarShowTimes.sync_api()
        except Exception:
            cache.set(constants.CACHE_KEY_GCAL_LAST_SYNC, "failed, please check your settings and try again.", timeout=None)
            raise
        else:
            cache.set(constants.CACHE_KEY_GCAL_LAST_SYNC, timezone.now(), timeout=None)
    else:
        logger.info('Synchronization with Google Calendar API disabled by config')
