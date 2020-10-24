import logging
import os
import shutil
import subprocess
import time

import huey
import pytz

from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import localtime, now

from constance import config
from huey.contrib import djhuey

from .liquidsoap import Liquidsoap
from .models import GoogleCalendarShowTimes, PrerecordedBroadcast


logger = logging.getLogger(__name__)


@djhuey.db_task()
def play_prerecorded_broadcast(prerecorded_broadcast):
    try:
        file_url = f'file://{prerecorded_broadcast.asset.file.path}'

        # TODO: have a thread local / open telnet per worker
        liquidsoap = Liquidsoap()
        liquidsoap.request__push(file_url)

        PrerecordedBroadcast.objects.filter(id=prerecorded_broadcast.id).update(status=PrerecordedBroadcast.Status.PLAYED)

    except Exception:
        PrerecordedBroadcast.objects.filter(id=prerecorded_broadcast.id).update(status=PrerecordedBroadcast.Status.FAILED)
        raise


@djhuey.db_task(context=True, retries=3, retry_delay=5)
def download_external_url(asset, url, title='', task=None):
    asset_cls = type(asset)
    asset_cls.objects.filter(id=asset.id).update(status=asset_cls.Status.RUNNING)

    try:
        # Upgrade / install youtube-dl once per day
        if not cache.get('ydl:up2date') or not shutil.which('youtube-dl'):
            logger.info('youtube-dl not updated in last 24 hours. Updating.')
            subprocess.run(['pip', 'install', '--upgrade', 'youtube-dl'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cache.set('ydl:up2date', True, timeout=60 * 60 * 24)

        logger.info(f'Running youtube-dl for {url}')
        args = ['youtube-dl', '--newline', '--extract-audio', '--no-playlist', '--max-downloads', '1', '--audio-format',
                config.EXTERNAL_ASSET_ENCODING, '--output', f'{settings.MEDIA_ROOT}/external/%(title)s.%(ext)s',
                '--no-continue', '--exec', 'echo {}']
        if config.EXTERNAL_ASSET_ENCODING != 'flac':
            args += ['--audio-quality', config.EXTERNAL_ASSET_BITRATE]

        cmd = subprocess.Popen(args + ['--', url], stdout=subprocess.PIPE, text=True)

        # log progress to cache for UI + logger
        last_dl_log_time = 0.0
        for line in cmd.stdout:
            line = line.removesuffix('\n')
            if not line.startswith('[download]') or (time.time() - last_dl_log_time >= 2.5):
                logger.info(f'youtube-dl: {line}')
                cache.set(f'ydl-log:{task.id}', line)
                last_dl_log_time = time.time()

        return_code = cmd.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, cmd)

        if os.path.exists(line):
            asset.title = title
            asset.file = line.removeprefix(f'{settings.MEDIA_ROOT}/')
            asset.status = asset_cls.Status.UPLOADED
            asset.save()
            logger.info(f'{url} successfully downloaded to {line}')

        else:
            raise Exception(f'youtube-dl reported downloaded file {line!r}, but it does not exist!')

    except Exception:
        if task.retries == 0:
            asset.title = f'Failed to download {url}'
            asset.status = asset_cls.Status.FAILED
            asset.save()

        raise


def crontab_and_startup(*args, **kwargs):
    needs_to_run = True
    crontab = huey.crontab(*args, **kwargs)

    def startup_crontab(dt):
        nonlocal needs_to_run
        if needs_to_run:
            needs_to_run = False
            return True
        else:
            return crontab(dt)

    return startup_crontab


@djhuey.db_periodic_task(crontab_and_startup(minute='*/15'))
@djhuey.lock_task('sync-google-calendar-api-lock')
def sync_google_calendar_api():
    if config.GOOGLE_CALENDAR_ENABLED:
        logger.info('Synchronizing with Google Calendar API')
        try:
            GoogleCalendarShowTimes.sync_api()
        except Exception:
            cache.set('gcal:last-sync', "failed, please check your settings and try again.", timeout=None)
            raise
        else:
            cache.set('gcal:last-sync', now(), timeout=None)
    else:
        logger.info('Synchronization with Google Calendar API disabled by config')


def local_daily_task(hour, minute=0, sunday_only=False):
    def test(datetime_utc):
        datetime_local = localtime(pytz.utc.localize(datetime_utc))
        print(
             datetime_local.hour == hour and datetime_local.minute == minute
             and (not sunday_only or datetime_local.weekday() == 6))
        return True
    return test
