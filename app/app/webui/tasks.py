import logging
import time

from django_redis import get_redis_connection
from huey.contrib import djhuey

from carb import constants
from services.services import ZoomService

logger = logging.getLogger(f"carb.{__name__}")


@djhuey.db_task(priority=5)
def stop_zoom_broadcast():
    logger.info("Stopping Zoom broadcast")

    redis = get_redis_connection()
    redis.delete(constants.REDIS_KEY_ROOM_INFO)
    # Wait for zoom-runner to cleanly quit room once redis key deleted
    # Don't feel good about tying up a Huey thread for 10 seconds, but stopping
    # Zoom is a rare enough occurrence that it's okay.
    time.sleep(10)

    service = ZoomService()
    service.supervisorctl("stop", "zoom", "zoom-runner")
