from huey.contrib.djhuey import db_periodic_task, db_task
import pytz

from django.utils.timezone import get_default_timezone

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


def once_per_day_local(hour, minute=0):
    def test(utc_dt):
        local_time = pytz.utc.localize(utc_dt).astimezone(get_default_timezone()).time()
        return local_time.hour == hour and local_time.minute == minute
    return test


@db_periodic_task(once_per_day_local(2))
def some_daily_cleanup():
    print('I ran at 2am')
