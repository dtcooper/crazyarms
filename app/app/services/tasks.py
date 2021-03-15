import datetime
import logging

from huey import crontab
import requests

from django.conf import settings
from django.utils import timezone

from constance import config
from huey.contrib import djhuey

from common.models import User
from common.tasks import local_daily_task

from .models import PlayoutLogEntry, UpstreamServer
from .services import init_services

logger = logging.getLogger(f"crazyarms.{__name__}")


LIQUIDSOAP_HEALTHCHECK_TIMEOUT = 5  # in seconds


@djhuey.periodic_task(priority=1, validate_datetime=local_daily_task(hour=3, minute=30))  # daily @ 3:30am local time
def purge_playout_log_entries():
    if config.PLAYOUT_LOG_PURGE_DAYS > 0:
        purge_less_than_datetime = timezone.now() - datetime.timedelta(days=config.PLAYOUT_LOG_PURGE_DAYS)
        num_deleted, _ = PlayoutLogEntry.objects.filter(created__lt=purge_less_than_datetime).delete()
        logger.info(f"purged {num_deleted} playout log entries {config.PLAYOUT_LOG_PURGE_DAYS} days or older.")
    else:
        logger.info("keeping playout log entries due to configuration (PLAYOUT_LOG_PURGE_DAYS <= 0)")


@djhuey.periodic_task(crontab(minute="*/2"))
def liquidsoap_services_watchdog(force=False):
    if User.objects.exists():
        services_to_check = [("harbor", "harbor", 8001)]
        services_to_check.extend(("upstream", u.name, u.healthcheck_port) for u in UpstreamServer.objects.all())

        if force or not settings.DEBUG:
            for service, subservice, port in services_to_check:
                response = None

                try:
                    response = requests.get(f"http://{service}:{port}/ping", timeout=LIQUIDSOAP_HEALTHCHECK_TIMEOUT)
                except Exception:
                    logger.exception(f"{service}:{subservice} healthcheck threw exception")

                if response and response.status_code == 200 and response.text == "pong":
                    logger.info(f"{service}:{subservice} healthcheck passed")
                else:
                    logger.info(f"{service}:{subservice} healthcheck failed. Restarting.")
                    init_services(services=service, subservices=subservice)
        else:
            logger.info("Liquidsoap services healthcheck disabled in DEBUG mode")
    else:
        logger.info("Liquidsoap services health check won't run when no user exists (pre-first run)")
