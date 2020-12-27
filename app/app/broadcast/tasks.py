import logging

from huey.contrib import djhuey

from services.liquidsoap import harbor

from .models import Broadcast

logger = logging.getLogger(f"carb.{__name__}")


@djhuey.db_task(priority=5, context=True, retries=10, retry_delay=2)
def play_broadcast(broadcast, task=None):
    try:
        harbor.prerecord__push(f"file://{broadcast.asset.file.path}")

        Broadcast.objects.filter(id=broadcast.id).update(status=Broadcast.Status.PLAYED)
    except Exception:
        if task is None or task.retries == 0:
            logger.error(f"Failed to broadcast {broadcast}")
            Broadcast.objects.filter(id=broadcast.id).update(status=Broadcast.Status.FAILED)
        raise
