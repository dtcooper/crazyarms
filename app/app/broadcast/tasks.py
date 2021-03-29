import logging

from huey.contrib import djhuey

from services.liquidsoap import harbor

from .models import Broadcast

logger = logging.getLogger(f"crazyarms.{__name__}")


@djhuey.db_task(priority=5, context=True, retries=10, retry_delay=2)
def play_broadcast(broadcast, task=None):
    try:
        broadcast.refresh_from_db()

        uri = broadcast.asset.liquidsoap_uri()
        if uri:
            harbor.prerecord__push(uri)
        else:
            raise Exception("Broadcast asset doesn't have a URI. Not sending to liquidsoap.")

        Broadcast.objects.filter(id=broadcast.id).update(status=Broadcast.Status.PLAYED)
        logger.info(f"Sent broadcast asset to harbor: {broadcast.asset}")
    except Exception:
        if task is None or task.retries == 0:
            logger.exception(f"Failed to broadcast {broadcast}")
            Broadcast.objects.filter(id=broadcast.id).update(status=Broadcast.Status.FAILED)
        raise
