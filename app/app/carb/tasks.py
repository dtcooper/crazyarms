import os

from celery import Celery

import django


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

app = Celery('carb')
app.config_from_object('django.conf:settings', namespace='CELERY')


from .models import ScheduledGCalShow  # noqa: E402


@app.task()
def tester():
    print(f'num: {ScheduledGCalShow.objects.count()}')
    import ipdb; ipdb.set_trace()
