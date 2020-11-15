import datetime
import logging

from django.utils import timezone

from constance import config
from huey.contrib import djhuey

from common.tasks import local_daily_task

from .models import PlayoutLogEntry


logger = logging.getLogger(f'carb.{__name__}')


@djhuey.periodic_task(local_daily_task(hour=3, minute=30))  # daily @ 3:30am local time
def purge_playout_log_entries():
    if config.PLAYOUT_LOG_PURGE_DAYS > 0:
        purge_less_than_datetime = timezone.now() - datetime.timedelta(days=config.PLAYOUT_LOG_PURGE_DAYS)
        num_deleted, _ = PlayoutLogEntry.objects.filter(created__lt=purge_less_than_datetime).delete()
        logger.info(f'purged {num_deleted} playout log entries {config.PLAYOUT_LOG_PURGE_DAYS} days or older.')
    else:
        logger.info('keeping playout log entries due to configuration (PLAYOUT_LOG_PURGE_DAYS <= 0)')
