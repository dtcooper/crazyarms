from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from constance.test import override_config
from django_redis import get_redis_connection

from crazyarms import constants

from .models import AudioAsset


@patch("autodj.models.random.sample", lambda l, n: list(l)[:n])  # Deterministic
class AntiRepeatTests(TestCase):
    def setUp(self):
        redis = get_redis_connection()
        redis.flushdb()

    @staticmethod
    def create_assets(num_tracks_per_artist=1, num_artists=1):
        assets = []
        for a in range(num_artists):
            for t in range(num_tracks_per_artist):
                asset = AudioAsset(
                    title=f"T:{a * num_tracks_per_artist + t}",
                    artist=f"A:{a}",
                    status=AudioAsset.Status.READY,
                )
                asset.save()
                assets.append(asset)
        return assets

    @staticmethod
    def get_no_repeat_artists():
        return cache.get(constants.CACHE_KEY_AUTODJ_NO_REPEAT_ARTISTS)

    @staticmethod
    def get_no_repeat_track_ids():
        return cache.get(constants.CACHE_KEY_AUTODJ_NO_REPEAT_IDS)

    @override_config(
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT=5,
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST=3,
    )
    def test_basic_no_repeat(self):
        tracks = self.create_assets(2, 4)

        played_track_names = [str(AudioAsset.get_next_for_autodj()) for _ in range(10)]
        self.assertEqual(
            played_track_names,
            [
                "A:0 - T:0",
                "A:1 - T:2",
                "A:2 - T:4",
                "A:3 - T:6",
                # We allow a repeat after 3 artists
                "A:0 - T:1",
                # We would have allowed a track repeat here, but that would involve artist repetation
                "A:1 - T:3",
                "A:2 - T:5",
                "A:3 - T:7",
                # Finally we get our repeats
                "A:0 - T:0",
                "A:1 - T:2",
            ],
        )

        self.assertEqual(self.get_no_repeat_track_ids(), [tracks[i].id for i in (2, 0, 7, 5, 3)])
        self.assertEqual(
            self.get_no_repeat_artists(),
            [AudioAsset.normalize_artist(f"A:{a}") for a in (1, 0, 3)],
        )

        # Try one more and see if our cache values as expected
        self.assertEqual(str(AudioAsset.get_next_for_autodj()), "A:2 - T:4")
        self.assertEqual(self.get_no_repeat_track_ids(), [tracks[i].id for i in (4, 2, 0, 7, 5)])
        self.assertEqual(
            self.get_no_repeat_artists(),
            [AudioAsset.normalize_artist(f"A:{a}") for a in (2, 1, 0)],
        )

    @override_config(
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT=0,
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST=0,
    )
    def test_disabled_when_set_to_zero(self):
        self.create_assets(2, 2)

        played_track_names = [str(AudioAsset.get_next_for_autodj()) for _ in range(3)]
        self.assertEqual(played_track_names, ["A:0 - T:0"] * 3)
        self.assertIsNone(self.get_no_repeat_artists())
        self.assertIsNone(self.get_no_repeat_track_ids())

    @override_config(
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT=0,
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST=2,
    )
    def test_no_artist_repeats_only(self):
        self.create_assets(2, 3)
        played_track_names = [str(AudioAsset.get_next_for_autodj()) for _ in range(5)]
        self.assertEqual(
            played_track_names,
            ["A:0 - T:0", "A:1 - T:2", "A:2 - T:4", "A:0 - T:0", "A:1 - T:2"],
        )

    @override_config(
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT=2,
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST=3,
    )
    def test_no_track_repeats_only(self):
        self.create_assets(3, 1)
        played_track_names = [str(AudioAsset.get_next_for_autodj()) for _ in range(5)]
        self.assertEqual(
            played_track_names,
            ["A:0 - T:0", "A:0 - T:1", "A:0 - T:2", "A:0 - T:0", "A:0 - T:1"],
        )

    @override_config(
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT=5,
        AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST=3,
    )
    def test_corner_cases_when_anti_repeat_not_possible(self):
        # No assets exist
        with self.assertLogs("crazyarms.autodj.models", level="INFO") as logger:
            self.assertIsNone(AudioAsset.get_next_for_autodj())
        self.assertEqual(
            logger.output,
            ["WARNING:crazyarms.autodj.models:autodj: no assets exist (no min/max id), giving up early"],
        )

        # Should only work on status = READY
        AudioAsset(status=AudioAsset.Status.PENDING).save()
        with self.assertLogs("crazyarms.autodj.models", level="INFO") as logger:
            self.assertIsNone(AudioAsset.get_next_for_autodj())
        self.assertEqual(
            logger.output,
            ["WARNING:crazyarms.autodj.models:autodj: no assets exist, giving up early"],
        )

        self.create_assets(2, 1)
        with self.assertLogs("crazyarms.autodj.models", level="INFO") as logger:
            self.assertEqual(str(AudioAsset.get_next_for_autodj()), "A:0 - T:0")
        self.assertEqual(logger.output, ["INFO:crazyarms.autodj.models:autodj: selected A:0 - T:0"])

        with self.assertLogs("crazyarms.autodj.models", level="INFO") as logger:
            self.assertEqual(str(AudioAsset.get_next_for_autodj()), "A:0 - T:1")
        self.assertEqual(
            logger.output,
            [
                "WARNING:crazyarms.autodj.models:autodj: no track found, attempting to run with artist repeats",
                "INFO:crazyarms.autodj.models:autodj: selected A:0 - T:1",
            ],
        )

        with self.assertLogs("crazyarms.autodj.models", level="INFO") as logger:
            self.assertEqual(str(AudioAsset.get_next_for_autodj()), "A:0 - T:0")
        self.assertEqual(
            logger.output,
            [
                "WARNING:crazyarms.autodj.models:autodj: no track found, attempting to run with artist repeats",
                "WARNING:crazyarms.autodj.models:autodj: no track found, attempting to run with artist and track"
                " repeats",
                "INFO:crazyarms.autodj.models:autodj: selected A:0 - T:0",
            ],
        )
