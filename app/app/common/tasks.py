import logging
import os
import shlex
import shutil
import subprocess
import time

import pytz

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from constance import config
from huey.contrib import djhuey


logger = logging.getLogger(f'carb.{__name__}')
YDL_PKG = 'https://github.com/blackjack4494/yt-dlc/archive/master.zip'
YDL_CMD = 'youtube-dlc'


@djhuey.db_task(context=True, retries=3, retry_delay=5)
def asset_download_external_url(asset, url, title='', task=None):
    asset_cls = type(asset)
    asset_cls.objects.filter(id=asset.id).update(status=asset_cls.Status.RUNNING)

    try:
        # Upgrade / install youtube-dl once per day
        if not cache.get('ydl:up2date') or not shutil.which(YDL_CMD):
            logger.info('youtube-dl: not updated in last 24 hours. Updating.')
            subprocess.run(['pip', 'install', '--upgrade', YDL_PKG], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cache.set('ydl:up2date', True, timeout=60 * 60 * 24)

        args = [YDL_CMD, '--newline', '--extract-audio', '--no-playlist', '--max-downloads', '1', '--audio-format',
                config.EXTERNAL_ASSET_ENCODING, '--output', f'{settings.MEDIA_ROOT}/external/%(title)s.%(ext)s',
                '--no-continue', '--add-metadata', '--exec', 'echo {}']
        if config.EXTERNAL_ASSET_ENCODING != 'flac':
            args += ['--audio-quality', config.EXTERNAL_ASSET_BITRATE]

        args += ['--', url]
        logger.info(f'youtube-dl: running: {shlex.join(args)}')
        cmd = subprocess.Popen(args, stdout=subprocess.PIPE, text=True)

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
            logger.info(f'youtube-dl: {url} successfully downloaded to {line}')

        else:
            raise Exception(f'youtube-dl reported downloaded file {line!r}, but it does not exist!')

    except Exception:
        if task.retries == 0:
            asset.title = f'Failed to download {url}'
            asset.status = asset_cls.Status.FAILED
            asset.save()

        raise


# TODO: is this used?
def local_daily_task(hour, minute=0, sunday_only=False):
    def test(datetime_utc):
        datetime_local = timezone.localtime(pytz.utc.localize(datetime_utc))
        print(
             datetime_local.hour == hour and datetime_local.minute == minute
             and (not sunday_only or datetime_local.weekday() == 6))
        return True
    return test
