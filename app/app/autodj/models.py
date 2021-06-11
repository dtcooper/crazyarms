import datetime
import logging
import random

import unidecode

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from constance import config

from common.models import AudioAssetBase, TruncatingCharField
from crazyarms import constants

logger = logging.getLogger(f"crazyarms.{__name__}")
RANDOM_CHUNK_TRIES = 15
RANDOM_CHUNK_SIZE = 250
STOPSET_CACHE_TIMEOUT = REQUESTS_CACHE_TIMEOUT = 2 * 60 * 60
ANTI_REPEAT_CACHE_TIMEOUT = 24 * 60 * 60


def random_queryset_pick(queryset):
    model_cls = queryset.model
    id_range = model_cls.objects.aggregate(min=models.Min("id"), max=models.Max("id"))
    min_id, max_id = id_range["min"], id_range["max"]

    if min_id is None or max_id is None:
        logger.warning(f"AutoDJ couldn't generate a random {model_cls._meta.verbose_name}, no assets exist")
        return None

    # We've got our query set, we're ready to pick our track
    # Generate chunk size * number of tries to get a set potential random IDs
    random_ids = random.sample(
        range(min_id, max_id + 1),
        min(RANDOM_CHUNK_TRIES * RANDOM_CHUNK_SIZE, max_id + 1 - min_id),
    )

    # Try for assets in the potential random ID set in chunks.
    for i in range(0, len(random_ids), RANDOM_CHUNK_SIZE):
        random_ids_chunk = random_ids[i : i + RANDOM_CHUNK_SIZE]

        # Preserve random ordering in query and take the first one that exists
        random_order = models.Case(*[models.When(id=id, then=pos) for pos, id in enumerate(random_ids_chunk)])
        pick = queryset.filter(id__in=random_ids_chunk).order_by(random_order).first()
        if pick:
            return pick

    logger.warning(f"AutoDJ couldn't generate a random {model_cls._meta.verbose_name}")
    return None


def normalize_title_field(value):
    return (" ".join(unidecode.unidecode(value).strip().split())).lower()


class AudioAsset(AudioAssetBase):
    TITLE_FIELDS = ("title", "artist", "album")
    TITLE_FIELDS_PRINT_SORTED = ("artist", "album", "title")
    artist = TruncatingCharField(
        "artist",
        max_length=255,
        blank=True,
        help_text="If left empty, an artist will be generated from the file's metadata.",
    )
    album = TruncatingCharField(
        "album",
        max_length=255,
        blank=True,
        help_text="If left empty, an album will be generated from the file's metadata.",
    )
    title_normalized = TruncatingCharField(max_length=255, db_index=True)
    artist_normalized = TruncatingCharField(max_length=255, db_index=True)
    album_normalized = TruncatingCharField(max_length=255, db_index=True)

    class Meta:
        ordering = ("title", "artist", "album", "id")
        verbose_name = "audio asset"
        verbose_name_plural = "audio assets"

    def clean(self, allow_conversion=True):
        super().clean(allow_conversion=allow_conversion)

        for field in self.TITLE_FIELDS:
            if field in self.get_dirty_fields():
                setattr(
                    self,
                    f"{field}_normalized",
                    normalize_title_field(getattr(self, field)),
                )

        # Only run if there is a title + artist
        if config.ASSET_DEDUPING and self.title_normalized and self.artist_normalized:
            match = (
                AudioAsset.objects.exclude(id=self.id)
                .filter(
                    status=self.Status.READY,
                    artist_normalized=self.artist_normalized,
                    album_normalized=self.album_normalized,
                    title_normalized=self.title_normalized,
                )
                .first()
            )
            if match:
                raise ValidationError(
                    f"A duplicate audio file already exists with the same artist, title (and album): {match}"
                )

    def queue_autodj_request(self):
        requests = cache.get(constants.CACHE_KEY_AUTODJ_REQUESTS, [])
        if len(requests) >= config.AUTODJ_REQUESTS_NUM or self.id in requests:
            logger.info(f"attempted to make autodj request {self}, but queue full or request exists")
            return False
        else:
            requests.append(self.id)
            cache.set(
                constants.CACHE_KEY_AUTODJ_REQUESTS,
                requests,
                timeout=REQUESTS_CACHE_TIMEOUT,
            )
            logger.info(f"queue autodj request {self}")
            return True

    @classmethod
    def process_anti_repeat_autodj(cls, audio_asset):
        if config.AUTODJ_ANTI_REPEAT_ENABLED:
            for conf_amount, cache_key, attr in (
                (
                    config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT,
                    constants.CACHE_KEY_AUTODJ_NO_REPEAT_IDS,
                    "id",
                ),
                (
                    config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST,
                    constants.CACHE_KEY_AUTODJ_NO_REPEAT_ARTISTS,
                    "artist_normalized",
                ),
            ):
                if conf_amount > 0:
                    no_repeat_list = cache.get(cache_key) or []
                    value = getattr(audio_asset, attr)  # Skip for blank artists
                    if value:
                        no_repeat_list.insert(0, value)
                    no_repeat_list = no_repeat_list[0:conf_amount]
                    cache.set(cache_key, no_repeat_list, timeout=ANTI_REPEAT_CACHE_TIMEOUT)

        return audio_asset

    @classmethod
    def get_next_for_autodj(
        cls,
        run_with_playlist=True,
        run_no_repeat_artists=True,
        run_no_repeat_track_ids=True,
    ):
        audio_asset = playlist = None

        # Deal with autodj requests
        requests = cache.get(constants.CACHE_KEY_AUTODJ_REQUESTS)
        if requests:
            request_id = requests.pop(0)
            cache.set(
                constants.CACHE_KEY_AUTODJ_REQUESTS,
                requests,
                timeout=REQUESTS_CACHE_TIMEOUT,
            )
            try:
                audio_asset = cls.objects.get(id=request_id)
            except AudioAsset.DoesNotExist:
                logger.warnining(f"request with audio asset id = {request_id} doesn't exist")
            else:
                logger.info(f"selected {audio_asset} from autodj request queue")
                return cls.process_anti_repeat_autodj(audio_asset)

        if not config.AUTODJ_ANTI_REPEAT_ENABLED:
            # If anti-repeat is enabled, we don't run these things
            run_no_repeat_artists = run_no_repeat_track_ids = False

        # Or if they're set to 0
        if run_no_repeat_artists and config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST <= 0:
            run_no_repeat_artists = False
        if run_no_repeat_track_ids and config.AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT <= 0:
            run_no_repeat_track_ids = False

        queryset = cls.objects.filter(status=AudioAsset.Status.READY)
        if not queryset.exists():
            logger.warning("no assets exist, giving up early")
            return None

        if config.AUTODJ_PLAYLISTS_ENABLED:
            # Only select from active playlists with at least one uploaded audio asset in them
            playlists_with_assets = list(
                Playlist.objects.filter(is_active=True, audio_assets__status=AudioAsset.Status.READY).distinct()
            )
            if run_with_playlist and not playlists_with_assets:
                run_with_playlist = False

            if run_with_playlist:
                # Select a playlist at random, applying its weighting
                playlists = list(playlists_with_assets)
                playlist = random.choices(playlists, weights=[p.weight for p in playlists], k=1)[0]
                queryset = queryset.filter(playlists=playlist)

            elif playlists_with_assets:
                # Otherwise select from all playlists (this excludes assets not in playlists)
                queryset = queryset.filter(playlists__in=playlists_with_assets)

            else:
                # If no playlists with assets exist, we don't filter by them
                logger.warning("no playlist with assets exists, so not filtering by playlist")
        else:
            run_with_playlist = False

        if run_no_repeat_artists:
            # Exclude from repeated artists
            no_repeat_artists = cache.get(constants.CACHE_KEY_AUTODJ_NO_REPEAT_ARTISTS)
            if no_repeat_artists:
                queryset = queryset.exclude(artist_normalized__in=no_repeat_artists)

        if run_no_repeat_track_ids:
            # Exclude from repeated tracks
            no_repeat_ids = cache.get(constants.CACHE_KEY_AUTODJ_NO_REPEAT_IDS)
            if no_repeat_ids:
                queryset = queryset.exclude(id__in=no_repeat_ids)

        # We've got our query set, we're ready to pick our track randomly
        audio_asset = random_queryset_pick(queryset)
        if audio_asset is not None:
            # We found a random asset. Process it and return to either recursive calls or directly
            logger.info(
                f"selected {audio_asset} "
                f"({f'selected from playlist {playlist}' if playlist else 'did not use a playlist'})"
            )
            return cls.process_anti_repeat_autodj(audio_asset)

        # We couldn't find a track, so we need to un-apply our filters
        # There are if/elif clauses. We're recursing and we need to hit the base case
        if run_with_playlist:
            # First recurse, use all playlists instead of filtering by chosen one
            logger.warning(f"no track found in {playlist}, attempting to run with all playlists")
            audio_asset = cls.get_next_for_autodj(
                run_with_playlist=False,
                run_no_repeat_artists=run_no_repeat_artists,
                run_no_repeat_track_ids=run_no_repeat_track_ids,
            )

        elif run_no_repeat_artists:
            # Second recurse without artist skips
            logger.warning("no track found, attempting to run with artist repeats")
            audio_asset = cls.get_next_for_autodj(
                run_with_playlist=False,
                run_no_repeat_artists=False,
                run_no_repeat_track_ids=run_no_repeat_track_ids,
            )

        elif run_no_repeat_track_ids:
            # Finally recurse without track ID skips
            logger.warning("no track found, attempting to run with artist and track repeats")
            audio_asset = cls.get_next_for_autodj(
                run_with_playlist=False,
                run_no_repeat_artists=False,
                run_no_repeat_track_ids=False,
            )

        if audio_asset is None:
            logger.warning("no track found, giving up")

        return audio_asset


class PlaylistStopsetBase(models.Model):
    name = models.CharField("name", max_length=100, unique=True)
    weight = models.FloatField(
        "random weight",
        validators=[MinValueValidator(0.00001)],
        default=1.0,
        help_text=(
            "The weight "
            "(ie selection bias) for how likely random selection from this playlist/stopset occurs, "
            "eg '1.0' is just as likely as all others, '2.0' is 2x as likely, '3.0' is 3x as "
            "likely, '0.5' half as likely, and so on. If unsure, leave as '1.0'."
        ),
    )
    is_active = models.BooleanField(
        "currently active",
        default=True,
        help_text=(
            "Whether tracks from this playlist/"
            "stopset will be selected. You may want to enable special playlists/stopsets at "
            "certain times, for example during the holidays."
        ),
    )

    def __str__(self):
        return self.name

    class Meta:
        abstract = True
        ordering = ("name",)


class Playlist(PlaylistStopsetBase):
    audio_assets = models.ManyToManyField(
        AudioAsset,
        related_name="playlists",
        db_index=True,
        verbose_name="audio assets",
        blank=True,
    )


class RotatorAsset(AudioAssetBase):
    UNNAMED_TRACK = "Untitled Asset"
    UPLOAD_DIR = "rotators"

    class Meta:
        ordering = ("title", "id")
        verbose_name = "rotator asset"
        verbose_name_plural = "rotator assets"

    @classmethod
    def get_next_for_autodj(cls, now=None):
        if now is None:
            now = timezone.now()

        asset = None

        current = cache.get(constants.CACHE_KEY_AUTODJ_CURRENT_STOPSET)
        if not current:
            should_generate = True
            last_run = cache.get(constants.CACHE_KEY_AUTODJ_STOPSET_LAST_FINISHED_AT)
            if last_run:
                should_generate = last_run + datetime.timedelta(minutes=config.AUTODJ_STOPSETS_ONCE_PER_MINUTES) <= now

            if should_generate:
                logger.info(f"{config.AUTODJ_STOPSETS_ONCE_PER_MINUTES} minutes since last stopset. Generating one.")
                current = Stopset.generate_random_rotator_asset_block()

        if current:
            stopset, rotator_and_asset_list = current

            while rotator_and_asset_list:
                rotator, asset = rotator_and_asset_list.pop(0)
                if asset:
                    logger.info(
                        f"Picked asset {asset} from rotator {rotator} in stopset {stopset}. "
                        f"{len(rotator_and_asset_list)} left to generate."
                    )
                    break

                else:
                    logger.warning(
                        f"Rotator {rotator} in {stopset} has no asset. {len(rotator_and_asset_list)} left to generate."
                    )

            if rotator_and_asset_list:
                cache.set(
                    constants.CACHE_KEY_AUTODJ_CURRENT_STOPSET,
                    (stopset, rotator_and_asset_list),
                    timeout=STOPSET_CACHE_TIMEOUT,
                )
            else:
                cache.delete(constants.CACHE_KEY_AUTODJ_CURRENT_STOPSET)
                finished_at = timezone.now()
                if asset:  # XXX Account for playtime to say this stopset finished after that
                    finished_at += asset.duration

                cache.set(
                    constants.CACHE_KEY_AUTODJ_STOPSET_LAST_FINISHED_AT,
                    finished_at,
                    timeout=STOPSET_CACHE_TIMEOUT,
                )

        return asset


class Rotator(models.Model):
    name = models.CharField("name", max_length=100, unique=True)
    rotator_assets = models.ManyToManyField(
        RotatorAsset,
        related_name="rotators",
        db_index=True,
        verbose_name="rotator assets",
        blank=True,
    )

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Stopset(PlaylistStopsetBase):
    def generate_rotator_asset_block(self):
        rotator_block = [s.rotator for s in StopsetRotator.objects.filter(stopset=self)]
        exclude_asset_ids = []
        rotator_asset_block = []

        for rotator in rotator_block:
            queryset = RotatorAsset.objects.filter(status=RotatorAsset.Status.READY, rotators=rotator).exclude(
                id__in=exclude_asset_ids
            )
            pick = random_queryset_pick(queryset)
            if pick:
                exclude_asset_ids.append(pick.id)
            else:
                logger.warning(f"Stopset {self} could not generate an asset for rotator {rotator}")
            rotator_asset_block.append((rotator, pick))

        return rotator_asset_block

    @classmethod
    def generate_random_rotator_asset_block(cls):
        stopsets = list(cls.objects.filter(is_active=True))

        # Randomly select a stopset, making sure it has at least one asset. Keep trying if it doesn't
        while stopsets:
            # Apply weighting when making a choice
            stopset = random.choices(stopsets, weights=[float(s.weight) for s in stopsets], k=1)[0]
            stopsets.remove(stopset)

            rotator_and_asset_list = stopset.generate_rotator_asset_block()
            if any(asset for _, asset in rotator_and_asset_list):
                return (stopset, rotator_and_asset_list)

            else:
                logger.info(f"No rotators or assets eligible to air found in stop set {stopset.name}.")

        logger.warning("No rotators or assets eligible to air in any active stopsets. No asset block generated.")
        return None


class StopsetRotator(models.Model):
    rotator = models.ForeignKey(Rotator, on_delete=models.CASCADE, related_name="stopset_rotators")
    stopset = models.ForeignKey(Stopset, on_delete=models.CASCADE, related_name="stopset_rotators")

    def __str__(self):
        s = f"{self.rotator.name} in {self.stopset.name}"
        if self.id:
            num = StopsetRotator.objects.filter(stopset=self.stopset, id__lte=self.id).count()
            s = f"Entry #{num}: {s}"
        return s

    class Meta:
        verbose_name = "rotator in stop set relationship"
        verbose_name_plural = "rotator in stop set relationships"
        # Very important, a lot is hedged on implicit ID ordering of these, ie admin interface, and block generation
        ordering = ("id",)


# For prettier admin text displays
Playlist.audio_assets.through.__str__ = lambda self: f"{self.audioasset.title} in playlist {self.playlist}"
Playlist.audio_assets.through._meta.verbose_name = "audio asset in playlist relationship"
Playlist.audio_assets.through._meta.verbose_name_plural = "audio asset in playlist relationships"
Rotator.rotator_assets.through.__str__ = lambda self: f"{self.rotatorasset.title} in rotator {self.rotator}"
Rotator.rotator_assets.through._meta.verbose_name = "rotator asset in rotator relationship"
Rotator.rotator_assets.through._meta.verbose_name_plural = "rotator asset in rotator relationship"
