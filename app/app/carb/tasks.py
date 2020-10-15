import os

from celery import Celery

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from .models import ScheduledBroadcast, PLAY_STATUS_PLAYED  # noqa: E402


app = Celery('carb')
app.config_from_object('django.conf:settings', namespace='CELERY')


@app.task()
def play_scheduled_broadcast(scheduled_broadcast_id):
    try:
        scheduled_broadcast = ScheduledBroadcast.objects.get(id=scheduled_broadcast_id)
        print(f'Would play: {scheduled_broadcast.asset_path}')
        ScheduledBroadcast.objects.filter(id=scheduled_broadcast_id).update(play_status=PLAY_STATUS_PLAYED)
    except ScheduledBroadcast.DoesNotExist:
        print(f'Scheduled broadcast does not exist [id={scheduled_broadcast_id}]')
