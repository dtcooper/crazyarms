import logging
import shutil
import subprocess

import huey
import pytz

from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import localtime

from constance import config
from huey.contrib import djhuey

from .liquidsoap import Liquidsoap
from .models import GoogleCalendarShow, PrerecordedBroadcast


logger = logging.getLogger(__name__)


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
        # Upgrade / install youtube-dl once per day
        if not cache.get('ydl:up2date') or not shutil.which('youtube-dl'):
            logger.info('youtube-dl not updated in last 24 hours. Updating.')
            subprocess.run(['pip', 'install', '--upgrade', 'youtube-dl'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cache.set('ydl:up2date', True, timeout=60 * 60 * 24)

        logger.info(f'Running youtube-dl for {url}')
        args = ['youtube-dl', '--newline', '--extract-audio', '--no-playlist', '--max-downloads', '1', '--audio-format',
                config.EXTERNAL_ASSET_ENCODING, '--output', f'{settings.MEDIA_ROOT}/external-download/%(title)s.%(ext)s',
                '--no-continue', '--exec', 'echo {}']
        if config.EXTERNAL_ASSET_ENCODING != 'flac':
            args += ['--audio-quality', config.EXTERNAL_ASSET_BITRATE]

        cmd = subprocess.Popen(args + ['--', url], stdout=subprocess.PIPE, text=True)
        for line in cmd.stdout:
            line = line.rstrip()
            logger.info(f'youtube-dl: {line}')
            cache.set(f'ydl:{task.id}', line)

        return_code = cmd.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, cmd)

        asset.title = title
        asset.file = line.removeprefix(f'{settings.MEDIA_ROOT}/')
        asset.file_status = asset_cls.FileStatus.UPLOADED
        asset.save()

    except Exception:
        if task.retries == 0:
            asset.file_status = asset_cls.FileStatus.FAILED
            asset.title = f'Failed to download {url}'
            asset.save()

        raise


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
