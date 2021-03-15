import datetime
import json
import traceback

import pytz

from django.core.management.base import BaseCommand
from django.conf import settings

from django_redis import get_redis_connection

from crazyarms.constants import REDIS_KEY_SERVICE_LOGS
from services.models import PlayoutLogEntry


class Command(BaseCommand):
    help = "Consume And Store Logs Messages From Redis"

    def handle(self, *args, **options):
        redis = get_redis_connection()

        self.stdout.write(f"Running log subscriber for redis key {REDIS_KEY_SERVICE_LOGS}...")

        while True:
            _, data = redis.brpop(REDIS_KEY_SERVICE_LOGS, timeout=0)

            try:
                log_entry_kwargs = json.loads(data)
                if not isinstance(log_entry_kwargs, dict):
                    raise ValueError

            except ValueError:
                self.stderr.write(f"Error decoding JSON in data: {data.decode()!r}")

            else:
                if settings.DEBUG:
                    self.stdout.write(f'Got message: {json.dumps(log_entry_kwargs, indent=2, sort_keys=True)}')

                if "created" in log_entry_kwargs:
                    try:
                        log_entry_kwargs["created"] = datetime.datetime.utcfromtimestamp(
                            float(log_entry_kwargs["created"])
                        ).replace(tzinfo=pytz.utc)
                    except ValueError:
                        pass

                try:
                    log_entry = PlayoutLogEntry(**log_entry_kwargs)
                    log_entry.full_clean()
                    log_entry.save()
                    self.stdout.write(f"Wrote log entry: {log_entry}")

                except Exception:
                    self.stderr.write(f"Uncaught exception creating log entry with kwargs: {log_entry_kwargs!r}:")
                    self.stderr.write(traceback.format_exc())
