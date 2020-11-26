import logging
import os
from urllib.parse import urlsplit

import requests

from django.conf import settings

from huey.contrib import djhuey

from autodj.models import AudioAsset


logger = logging.getLogger(f'carb.{__name__}')

NUM_SAMPLE_ASSETS = 75
CCMIXTER_API_URL = 'http://ccmixter.org/api/query'
# Ask for a few month, since we only want ones with mp3s
CCMIXTER_API_PARAMS = {'sinced': '1 month ago', 'sort': 'rank', 'f': 'js', 'limit': round(NUM_SAMPLE_ASSETS * 1.5)}


@djhuey.db_task()
def generate_sample_assets(uploader=None):
    logger.info(f'Downloading {NUM_SAMPLE_ASSETS} sample assets from ccMixter')
    tracks_json = requests.get(CCMIXTER_API_URL, params=CCMIXTER_API_PARAMS).json()
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
            mp3_path = f'{settings.MEDIA_ROOT}/ccmixter-sample/{os.path.basename(urlsplit(mp3_url).path)}'

            os.makedirs(f'{settings.MEDIA_ROOT}/ccmixter-sample', exist_ok=True)
            with open(mp3_path, 'wb') as mp3_file:
                response = requests.get(mp3_url, stream=True)
                for chunk in response.iter_content(chunk_size=4 * 1024):
                    mp3_file.write(chunk)

            audio_asset = AudioAsset(uploader=uploader)
            audio_asset.file = mp3_path.removeprefix(f'{settings.MEDIA_ROOT}/')
            audio_asset.save()

    logger.info(f'Done downloading {NUM_SAMPLE_ASSETS} sample assets from ccMixter')


@djhuey.db_task()
def stop_zoom_broadcast():
    print('would stop broadcast')
