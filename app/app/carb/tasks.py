import subprocess

import huey
import pytz

from django.conf import settings
from django.utils.timezone import localtime

from constance import config
from huey.contrib import djhuey

from .liquidsoap import Liquidsoap
from .models import GoogleCalendarShow, PrerecordedBroadcast


@djhuey.db_task()
def play_prerecorded_broadcast(object_id):
    obj = PrerecordedBroadcast.objects.get(id=object_id)

    try:
        file_url = f'file://{obj.asset.file.path}'

        # TODO: have a thread local / open telnet per worker
        liquidsoap = Liquidsoap()
        liquidsoap.request__push(file_url)

        PrerecordedBroadcast.objects.filter(id=object_id).update(play_status=PrerecordedBroadcast.PlayStatus.PLAYED)

    except Exception:
        PrerecordedBroadcast.objects.filter(id=object_id).update(play_status=PrerecordedBroadcast.PlayStatus.FAILED)

@djhuey.db_task(context=True, retries=3, retry_delay=5)
def download_external_url(asset_cls, object_id, url, title='', task=None):
    asset_cls.objects.filter(id=object_id).update(file_status=asset_cls.FileStatus.RUNNING)
    asset = asset_cls.objects.get(id=object_id)

    try:
        # Upgrade / install youtube-dl
        subprocess.run(['pip', 'install', '--upgrade', 'youtube-dl'], check=True)

        args = ['youtube-dl', '--quiet', '--extract-audio', '--no-playlist', '--max-downloads', '1', '--audio-format',
                config.EXTERNAL_ASSET_ENCODING, '--output', f'{settings.MEDIA_ROOT}/downloaded/%(title)s.%(ext)s',
                '--no-continue', '--exec', 'echo {}']
        if config.EXTERNAL_ASSET_ENCODING != 'flac':
            args += ['--audio-quality', config.EXTERNAL_ASSET_BITRATE]

        cmd = subprocess.run(args + ['--', url], check=True, capture_output=True)
        audio_file = cmd.stdout.decode().strip()

        asset.title = title
        asset.file = audio_file.removeprefix(f'{settings.MEDIA_ROOT}/')
        asset.file_status = asset_cls.FileStatus.UPLOADED
        asset.save()

    except Exception:
        if task.retries == 0:
            asset.file_status = asset_cls.FileStatus.FAILED
            asset.title = f'Failed to download {url}'
            asset.save()


@djhuey.db_periodic_task(huey.crontab(minute='*/15'))
@djhuey.lock_task('sync-google-calendar-api-lock')
def sync_google_calendar_api():
    if config.GOOGLE_CALENDAR_ENABLED:
        GoogleCalendarShow.sync_api()


def local_daily_task(hour, minute=0, sunday_only=False):
    def test(datetime_utc):
        datetime_local = localtime(pytz.utc.localize(datetime_utc))
        print(
             datetime_local.hour == hour and datetime_local.minute == minute
             and (not sunday_only or datetime_local.weekday() == 6))
        return True
    return test
