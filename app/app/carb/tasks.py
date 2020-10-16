from huey.contrib.djhuey import db_task

from .liquidsoap import Liquidsoap
from .models import ScheduledBroadcast, PLAY_STATUS_PLAYED


@db_task()
def play_scheduled_broadcast(scheduled_broadcast_id):
    scheduled_broadcast = ScheduledBroadcast.objects.get(id=scheduled_broadcast_id)
    print(f'Sending URL: {scheduled_broadcast.asset_path} [id={scheduled_broadcast_id}]')

    # TODO: have a thread local / open telnet per worker
    liquidsoap = Liquidsoap()
    liquidsoap.request__push(scheduled_broadcast.asset_path)

    ScheduledBroadcast.objects.filter(id=scheduled_broadcast_id).update(play_status=PLAY_STATUS_PLAYED)
