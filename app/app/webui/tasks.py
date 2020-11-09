import logging
import os
import tempfile
from urllib.parse import urlsplit

import requests

from django.core.files import File

from huey.contrib import djhuey

from autodj.models import AudioAsset


logger = logging.getLogger(f'carb.{__name__}')

NUM_SAMPLE_ASSETS = 50
CCMIXTER_API_URL = 'http://ccmixter.org/api/query'
# Ask for a few month, since we only want ones with mp3s
CCMIXTER_API_PARAMS = {'sinced': '1 month ago', 'sort': 'rank', 'f': 'js', 'limit': round(NUM_SAMPLE_ASSETS * 1.5)}


@djhuey.db_task()
def generate_sample_assets(uploader=None):
    logger.info(f'Downloading {NUM_SAMPLE_ASSETS} from ccMixter')
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
            with tempfile.TemporaryFile() as temp_file:
                response = requests.get(mp3_url, stream=True)
                for chunk in response.iter_content(chunk_size=4 * 1024):
                    temp_file.write(chunk)
                temp_file.seek(0)
                file = File(temp_file, name=f'ccmixter-sample/{os.path.basename(urlsplit(mp3_url).path)}')
                audio_asset = AudioAsset(file=file, uploader=uploader)
                audio_asset.save()

    logger.info(f'Done downloading {NUM_SAMPLE_ASSETS} sample assets from ccMixter')
