import logging
import random

import unidecode

from django.core.cache import cache
from django.db import models

from constance import config

from carb.constants import CACHE_KEY_AUTODJ_NO_REPEAT_ARTISTS, CACHE_KEY_AUTODJ_NO_REPEAT_IDS
from common.models import AudioAssetBase, TruncatingCharField


logger = logging.getLogger(f'carb.{__name__}')


class AudioAsset(AudioAssetBase):
    TITLE_FIELDS = ('title', 'artist', 'album')
    RANDOM_CHUNK_TRIES = 10
    RANDOM_CHUNK_SIZE = 25
    artist = TruncatingCharField('artist', max_length=255, blank=True,
                                 help_text="If left empty, an artist will be generated from the file's metadata.")
    artist_normalized = TruncatingCharField('artist', max_length=255, db_index=True)
    album = TruncatingCharField('album', max_length=255, blank=True,
                                help_text="If left empty, an album will be generated from the file's metadata.")

    def __str__(self):
        s = ' - '.join(filter(None, (getattr(self, field_name, None) for field_name in ('artist', 'album', 'title'))))
        return super().__str__(s)

    def save(self, *args, **kwargs):
        artist_normalized_before_save = self.artist_normalized
        super().save(*args, **kwargs)
        if self.artist_normalized == '' or artist_normalized_before_save != self.artist_normalized:
            self.artist_normalized = (' '.join(unidecode.unidecode(self.artist).strip().split())).lower()
        super().save(*args, **kwargs)

    @classmethod
    def process_anti_repeat_autodj(cls, audio_asset):
        if config.AUTODJ_ANTI_REPEAT:
            for conf_amount, cache_key, attr in (
                (config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT, CACHE_KEY_AUTODJ_NO_REPEAT_IDS, 'id'),
                (config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST, CACHE_KEY_AUTODJ_NO_REPEAT_ARTISTS,
                 'artist_normalized'),
            ):
                if conf_amount > 0:
                    no_repeat_list = cache.get(cache_key) or []
                    no_repeat_list.insert(0, getattr(audio_asset, attr))
                    no_repeat_list = no_repeat_list[0:conf_amount]
                    cache.set(cache_key, no_repeat_list, timeout=60 * 60 * 24)

        return audio_asset

    @classmethod
    def get_next_for_autodj(cls, run_no_repeat_artists=True, run_no_repeat_track_ids=True):
        id_range = cls.objects.aggregate(min=models.Min('id'), max=models.Max('id'))
        min_id, max_id = id_range['min'], id_range['max']
        if min_id is None or max_id is None:
            return None

        if not config.AUTODJ_ANTI_REPEAT:
            # If anti-repeat is enabled, we don't run these things
            run_no_repeat_artists = run_no_repeat_track_ids = False
        # Or if they're set to 0
        if run_no_repeat_artists and config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST <= 0:
            run_no_repeat_artists = False
        if run_no_repeat_track_ids and config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT <= 0:
            run_no_repeat_track_ids = False

        queryset = cls.objects.filter(status=AudioAsset.Status.UPLOADED)
        if not queryset.exists():
            logger.info('autodj: no assets exist, giving up early')
            return None

        if run_no_repeat_track_ids:
            no_repeat_ids = cache.get(CACHE_KEY_AUTODJ_NO_REPEAT_IDS)
            if no_repeat_ids:
                queryset = queryset.exclude(id__in=no_repeat_ids)

        if run_no_repeat_artists:
            no_repeat_artists = cache.get(CACHE_KEY_AUTODJ_NO_REPEAT_ARTISTS)
            if no_repeat_artists:
                queryset = queryset.exclude(artist_normalized__in=no_repeat_artists)

        # Generate chunk size * number of tries to get a set potential random IDs
        random_ids = random.sample(
            range(min_id, max_id + 1),
            min(cls.RANDOM_CHUNK_TRIES * cls.RANDOM_CHUNK_SIZE, max_id + 1 - min_id),
        )

        # Try for assets in the potential random ID set in chunks
        for i in range(0, len(random_ids), cls.RANDOM_CHUNK_SIZE):
            random_ids_chunk = random_ids[i:i + cls.RANDOM_CHUNK_SIZE]
            # Preserve random ordering in query and take the first one that exists
            random_order = models.Case(*[models.When(id=id, then=pos) for pos, id in enumerate(random_ids_chunk)])
            audio_asset = queryset.order_by(random_order).first()
            if audio_asset is not None:
                logger.info(f'autodj: selected {audio_asset}')
                return cls.process_anti_repeat_autodj(audio_asset)

        if run_no_repeat_artists and run_no_repeat_track_ids:
            # First recurse without artist skips, we won't this recursive block
            logger.info('autodj: no track found, attempting to run with artist repeats')
            audio_asset = cls.get_next_for_autodj(run_no_repeat_artists=False)
            if audio_asset is not None:
                return audio_asset

            # Then recurse without track ID skips, we won't hit this recursive block either
            logger.info('autodj: no track found, attempting to run with artist and track repeats')
            audio_asset = cls.get_next_for_autodj(run_no_repeat_artists=False, run_no_repeat_track_ids=False)
            if audio_asset is not None:
                return audio_asset

        logger.info('autodj: no track found, giving up')
        return None

    class Meta:
        verbose_name = 'audio asset'
        verbose_name_plural = 'audio assets'
