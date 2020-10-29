import logging

from huey.contrib import djhuey

from services.liquidsoap import harbor

from .models import Broadcast


logger = logging.getLogger(f'carb.{__name__}')


@djhuey.db_task()
def play_prerecorded_broadcast(prerecorded_broadcast):
    try:
        file_url = f'file://{prerecorded_broadcast.asset.file.path}'

        # TODO: have a thread local / open telnet per worker
        harbor.prerecorded__push(file_url)

        Broadcast.objects.filter(id=prerecorded_broadcast.id).update(
            status=Broadcast.Status.PLAYED)

    except Exception:
        Broadcast.objects.filter(id=prerecorded_broadcast.id).update(
            status=Broadcast.Status.FAILED)
        raise
