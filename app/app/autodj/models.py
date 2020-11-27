import logging
import random

import unidecode

from django.core.cache import cache
from django.core.validators import MinValueValidator
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

    @staticmethod
    def normalize_artist(artist):
        return (' '.join(unidecode.unidecode(artist).strip().split())).lower()

    def save(self, *args, **kwargs):
        artist_normalized_before_save = self.artist_normalized
        super().save(*args, **kwargs)
        if self.artist_normalized == '' or artist_normalized_before_save != self.artist_normalized:
            self.artist_normalized = self.normalize_artist(self.artist)
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
                    value = getattr(audio_asset, attr)
                    if value:
                        no_repeat_list.insert(0, value)
                    no_repeat_list = no_repeat_list[0:conf_amount]
                    cache.set(cache_key, no_repeat_list, timeout=60 * 60 * 24)

        return audio_asset

    @classmethod
    def get_next_for_autodj(cls, run_with_playlist=True, run_no_repeat_artists=True, run_no_repeat_track_ids=True):
        audio_asset = playlist = None

        id_range = cls.objects.aggregate(min=models.Min('id'), max=models.Max('id'))
        min_id, max_id = id_range['min'], id_range['max']

        if min_id is None or max_id is None:
            logger.warning('autodj: no assets exist (no min/max id), giving up early')
            return None

        if not config.AUTODJ_ANTI_REPEAT:
            # If anti-repeat is enabled, we don't run these things
            run_no_repeat_artists = run_no_repeat_track_ids = False
        # Or if they're set to 0
        if run_no_repeat_artists and config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST <= 0:
            run_no_repeat_artists = False
        if run_no_repeat_track_ids and config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT <= 0:
            run_no_repeat_track_ids = False

        # Only select from active playlists with at least one uploaded audio asset in them
        playlists_with_assets = list(Playlist.objects.filter(
            is_active=True, audio_assets__status=AudioAsset.Status.UPLOADED).distinct())
        if run_with_playlist and not playlists_with_assets:
            run_with_playlist = False

        queryset = cls.objects.filter(status=AudioAsset.Status.UPLOADED)
        if not queryset.exists():
            logger.warning('autodj: no assets exist, giving up early')
            return None

        if run_with_playlist:
            # Select a playlist at random according to its weight
            playlists = list(playlists_with_assets)
            playlist = random.choices(playlists, weights=[p.weight for p in playlists], k=1)[0]
            queryset = queryset.filter(playlists=playlist)

        elif playlists_with_assets:
            # Otherwise select from all playlists (this excludes assets not in playlists)
            queryset = queryset.filter(playlists__in=playlists_with_assets)

        else:
            # If no playlists with assets exist, we don't filter by them
            logger.warning('autodj: no playlist with assets exists, so not filtering by playlist')

        if run_no_repeat_artists:
            # Exclude from repeated artists
            no_repeat_artists = cache.get(CACHE_KEY_AUTODJ_NO_REPEAT_ARTISTS)
            if no_repeat_artists:
                queryset = queryset.exclude(artist_normalized__in=no_repeat_artists)

        if run_no_repeat_track_ids:
            # Exclude from repeated tracks
            no_repeat_ids = cache.get(CACHE_KEY_AUTODJ_NO_REPEAT_IDS)
            if no_repeat_ids:
                queryset = queryset.exclude(id__in=no_repeat_ids)

        # We've got our query set, we're ready to pick our track
        # Generate chunk size * number of tries to get a set potential random IDs
        random_ids = random.sample(
            range(min_id, max_id + 1),
            min(cls.RANDOM_CHUNK_TRIES * cls.RANDOM_CHUNK_SIZE, max_id + 1 - min_id),
        )

        # Try for assets in the potential random ID set in chunks.
        for i in range(0, len(random_ids), cls.RANDOM_CHUNK_SIZE):
            random_ids_chunk = random_ids[i:i + cls.RANDOM_CHUNK_SIZE]
            # Preserve random ordering in query and take the first one that exists
            random_order = models.Case(*[models.When(id=id, then=pos) for pos, id in enumerate(random_ids_chunk)])
            audio_asset = queryset.order_by(random_order).first()
            if audio_asset is not None:
                # We found a random asset. Process it and return to either recursive calls or directly
                logger.info(f'autodj: selected {audio_asset} '
                            f"({f'selected from playlist {playlist}' if playlist else 'did not use a playlist'})")
                return cls.process_anti_repeat_autodj(audio_asset)

        # We couldn't find a track, so we need to un-apply our filters
        # There are if/elif clauses. We're recursing and we need to hit the base case
        if run_with_playlist:
            # First recurse, use all playlists instead of filtering by chosen one
            logger.warning('autodj: no track found, attempting to run with all playlists')
            audio_asset = cls.get_next_for_autodj(run_with_playlist=False, run_no_repeat_artists=run_no_repeat_artists,
                                                  run_no_repeat_track_ids=run_no_repeat_track_ids)

        elif run_no_repeat_artists:
            # Second recurse without artist skips
            logger.warning('autodj: no track found, attempting to run with artist repeats')
            audio_asset = cls.get_next_for_autodj(run_with_playlist=False, run_no_repeat_artists=False,
                                                  run_no_repeat_track_ids=run_no_repeat_track_ids)

        elif run_no_repeat_track_ids:
            # Finally recurse without track ID skips
            logger.warning('autodj: no track found, attempting to run with artist and track repeats')
            audio_asset = cls.get_next_for_autodj(run_with_playlist=False, run_no_repeat_artists=False,
                                                  run_no_repeat_track_ids=False)

        if audio_asset is None:
            logger.warning('autodj: no track found, giving up')

        return audio_asset

    class Meta:
        verbose_name = 'audio asset'
        verbose_name_plural = 'audio assets'


class Playlist(models.Model):
    name = models.CharField('name', max_length=100, unique=True)
    weight = models.FloatField('random weight', validators=[MinValueValidator(0.0)], default=1., help_text='The weight '
                               "(ie selection bias) for how likely random selection from this playlist occurs, eg "
                               "'1.0' is just as likely as all others, '2.0' is 2x as likely, '3.0' is 3x as likely, "
                               "'0.5' half as likely, and so on. If unsure, leave as '1.0'.")
    is_active = models.BooleanField('currently active', default=True, help_text='Whether tracks from this playlist '
                                    'will are be selected. You may want to enable special playlists at certain times, '
                                    'for example during the holidays.')
    audio_assets = models.ManyToManyField(AudioAsset, related_name='playlists', db_index=True,
                                          verbose_name='audio assets', blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


# For prettier admin display
Playlist.audio_assets.through.__str__ = lambda self: f'{self.audioasset.title} in playlist {self.playlist}'
Playlist.audio_assets.through._meta.verbose_name = 'audio asset in playlist relationship'
Playlist.audio_assets.through._meta.verbose_name_plural = 'audio asset in playlist relationships'
