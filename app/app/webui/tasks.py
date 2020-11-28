import logging
import os
import subprocess
from urllib.parse import urlsplit
import time

import requests

from django.conf import settings

from constance import config
from django_redis import get_redis_connection
from huey.contrib import djhuey

from autodj.models import AudioAsset, Playlist, Rotator, RotatorAsset, StopsetRotator, Stopset
from carb import constants
from common.tasks import YDL_CMD, confirm_youtube_dl
from services.services import ZoomService


logger = logging.getLogger(f'carb.{__name__}')

SOUNDCLOUD_ASSETS_PLAYLIST_URL = 'https://soundcloud.com/dtcooper/sets/carb-sample-data/s-4Tlos8HM03B'
NUM_SAMPLE_ASSETS = 75
CCMIXTER_API_URL = 'http://ccmixter.org/api/query'
# Ask for a few month, since we only want ones with mp3s
CCMIXTER_API_PARAMS = {'sinced': '1 month ago', 'sort': 'rank', 'f': 'js', 'limit': round(NUM_SAMPLE_ASSETS * 1.5)}


@djhuey.db_task()
def generate_sample_stopsets(uploader=None):
    soundcloud_dir = f'{settings.MEDIA_ROOT}/stopset-sample'
    logger.info("Download rotator assets from SoundCloud (BMIR) using youtube-dl")

    confirm_youtube_dl()
    os.makedirs(soundcloud_dir, exist_ok=True)
    subprocess.run([YDL_CMD, '--quiet', '--yes-playlist', '--output', f'{soundcloud_dir}/%(title)s.%(ext)s',
                    SOUNDCLOUD_ASSETS_PLAYLIST_URL])

    files_downloaded = os.listdir(soundcloud_dir)
    num_downloaded = len(files_downloaded)

    if num_downloaded < 1:
        logger.info('Error downloading from SoundCloud. Ending prematurely.')
    logger.info(f'Downloaded {num_downloaded} from SoundCloud')

    # files are on SoundCloud are named psa-N.mp3 or station-id-N.mp3, or ad-N.mp3 so these keys match
    # get_or_create since name is unique
    rotators = {'psa': Rotator.objects.get_or_create(name='Sample Public Service Announcements')[0],
                'station-id': Rotator.objects.get_or_create(name='Sample Station IDs')[0],
                'ad': Rotator.objects.get_or_create(name='Sample Advertisements')[0]}

    for sample_file in files_downloaded:
        rotator = sample_file.rsplit('-', 1)[0]
        if rotator not in rotators:
            logger.info(f'Got malformed file from SoundCloud: {sample_file}. Skipping.')
            continue

        logger.info(f'Got {sample_file} from SoundCloud')
        rotator_asset = RotatorAsset(uploader=uploader)
        rotator_asset.file = f'{soundcloud_dir}/{sample_file}'.removeprefix(f'{settings.MEDIA_ROOT}/')
        rotator_asset.save()
        rotator = rotators[rotator]
        rotator.rotator_assets.add(rotator_asset)

    sample_stopsets = (
        ('station-id', 'ad', 'psa', 'ad', 'station-id'),
        ('station-id', 'ad', 'station-id'),
        ('station-id', 'ad', 'ad', 'station-id', 'psa'),
    )

    for n, rotator_list in enumerate(sample_stopsets, 1):
        # get_or_create since name is unique
        stopset = Stopset.objects.get_or_create(name=f'Sample Stopset #{n}')[0]
        StopsetRotator.objects.filter(stopset=stopset).delete()
        for rotator in rotator_list:
            StopsetRotator.objects.create(rotator=rotators[rotator], stopset=stopset)
    logger.info(f'Generated {len(sample_stopsets)} sample stop sets.')

    config.AUTODJ_STOPSETS_ENABLED = True
    logger.info('Done downloading sample data from SoundCloud. Set AUTODJ_STOPSETS_ENABLED = True.')


@djhuey.db_task()
def generate_sample_audio_assets(uploader=None):
    logger.info(f'Downloading {NUM_SAMPLE_ASSETS} sample audio assets from ccMixter')
    tracks_json = requests.get(CCMIXTER_API_URL, params=CCMIXTER_API_PARAMS).json()
    ccmixer_dir = f'{settings.MEDIA_ROOT}/ccmixter-sample'

    # get_or_create since name is unique
    playlist = Playlist.objects.get_or_create(name='ccMixter Sample Music')[0]
    num_downloaded = 0

    for track in tracks_json:
        try:
            mp3_url = next(f['download_url'] for f in track['files'] if f['download_url'].endswith('.mp3'))
        except StopIteration:
            pass
        else:
            num_downloaded += 1
            if num_downloaded > NUM_SAMPLE_ASSETS:
                break

            logger.info(f'Downloading sample asset {mp3_url} ({num_downloaded}/{NUM_SAMPLE_ASSETS})')
            mp3_path = f'{ccmixer_dir}/{os.path.basename(urlsplit(mp3_url).path)}'

            os.makedirs(ccmixer_dir, exist_ok=True)
            with open(mp3_path, 'wb') as mp3_file:
                response = requests.get(mp3_url, stream=True)
                for chunk in response.iter_content(chunk_size=4 * 1024):
                    mp3_file.write(chunk)

            audio_asset = AudioAsset(uploader=uploader)
            audio_asset.file = mp3_path.removeprefix(f'{settings.MEDIA_ROOT}/')
            audio_asset.save()
            audio_asset.playlists.add(playlist)
    logger.info(f'Done downloading {NUM_SAMPLE_ASSETS} sample audio assets from ccMixter')


@djhuey.db_task()
def stop_zoom_broadcast():
    logger.info('Stopping Zoom broadcast')

    redis = get_redis_connection()
    redis.delete(constants.REDIS_KEY_ROOM_INFO)
    # Wait for zoom-runner to cleanly quit room once redis key deleted
    # Don't feel good about tying up a Huey thread for 10 seconds, but stopping
    # Zoom is a rare enough occurrence that it's okay.
    time.sleep(10)

    service = ZoomService()
    service.supervisorctl('stop', 'zoom', 'zoom-runner')
