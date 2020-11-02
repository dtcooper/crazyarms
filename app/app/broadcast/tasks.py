import logging

from huey.contrib import djhuey

from services.liquidsoap import harbor

from .models import Broadcast


logger = logging.getLogger(f'carb.{__name__}')


@djhuey.db_task()
def play_broadcast(broadcast):
    try:
        harbor.prerecord__push(f'file://{broadcast.asset.file.path}')

        Broadcast.objects.filter(id=broadcast.id).update(
            status=Broadcast.Status.PLAYED)
    except Exception:
        Broadcast.objects.filter(id=broadcast.id).update(
            status=Broadcast.Status.FAILED)
        raise
