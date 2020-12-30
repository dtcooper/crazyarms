import datetime
import json
import logging

from dateutil.parser import parse
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from django.core.cache import cache
from django.db import models
from django.utils import timezone
from django.utils.formats import date_format

from constance import config

from carb import constants
from common.models import TruncatingCharField, User

logger = logging.getLogger(f"carb.{__name__}")


class GCalShow(models.Model):
    SYNC_RANGE_MIN = datetime.timedelta(days=60)
    SYNC_RANGE_MAX = datetime.timedelta(days=120)

    gcal_id = TruncatingCharField(max_length=256, unique=True)
    users = models.ManyToManyField(User, related_name="gcal_shows", verbose_name="users")
    title = TruncatingCharField("title", max_length=1024)
    start = models.DateTimeField("start time")
    end = models.DateTimeField("end time")

    def __str__(self):
        return (
            f"{self.title}: {date_format(timezone.localtime(self.start), 'SHORT_DATETIME_FORMAT')}"
            f" - {date_format(timezone.localtime(self.end), 'SHORT_DATETIME_FORMAT')}"
        )

    class Meta:
        ordering = ("start", "id")
        verbose_name = "Google Calendar show"
        verbose_name_plural = "Google Calendar shows"

    @staticmethod
    def get_last_sync():
        return cache.get(constants.CACHE_KEY_GCAL_LAST_SYNC)

    @classmethod
    def sync_api(cls):
        logger.info(
            f"Syncing with Google Calendar events API in -{cls.SYNC_RANGE_MIN.days} days,"
            f" +{cls.SYNC_RANGE_MAX.days} days range"
        )
        credentials = Credentials.from_service_account_info(json.loads(config.GOOGLE_CALENDAR_CREDENTIALS_JSON))
        service = build("calendar", "v3", credentials=credentials)

        email_to_user = {}  # lookup cache
        shows = []

        page_token = None
        while True:
            response = (
                service.events()
                .list(
                    calendarId=config.GOOGLE_CALENDAR_ID,
                    maxResults=2500,
                    timeMin=(datetime.datetime.utcnow() - cls.SYNC_RANGE_MIN).isoformat() + "Z",
                    timeMax=(datetime.datetime.utcnow() + cls.SYNC_RANGE_MAX).isoformat() + "Z",
                    timeZone="UTC",
                    singleEvents="true",
                    pageToken=page_token,
                )
                .execute()
            )

            for item in response["items"]:
                start = (
                    timezone.make_aware(parse(item["start"]["date"]), is_dst=False)
                    if item["start"].get("dateTime") is None
                    else parse(item["start"].get("dateTime"))
                )
                end = (
                    timezone.make_aware(
                        parse(item["end"]["date"]).replace(hour=23, minute=59, second=59),
                        is_dst=True,
                    )
                    if item["end"].get("dateTime") is None
                    else parse(item["end"].get("dateTime"))
                )

                emails = [attendee["email"] for attendee in item.get("attendees", [])]
                creator = item.get("creator", {}).get("email")
                if creator is not None:
                    emails.append(creator)

                users = []

                for email in emails:
                    user = email_to_user.get(email)
                    if not user:
                        try:
                            user = email_to_user[email] = User.objects.get(email=email)
                        except User.DoesNotExist:
                            pass

                    if user:
                        users.append(user)

                title = item.get("summary", "").strip()
                shows.append((item["id"], users, {"title": title, "start": start, "end": end}))

            page_token = response.get("nextPageToken")
            if page_token is None:
                break

        synced_gcal_ids = []

        for gcal_id, users, defaults in shows:
            gcal_show, _ = cls.objects.update_or_create(gcal_id=gcal_id, defaults=defaults)
            gcal_show.users.set(users)
            synced_gcal_ids.append(gcal_id)

        _, deleted_dict = cls.objects.exclude(gcal_id__in=synced_gcal_ids).delete()
        num_deleted = deleted_dict.get(f"{cls._meta.app_label}.{cls._meta.object_name}", 0)
        logger.info(f"Done. Synced {len(synced_gcal_ids)} shows, deleted {num_deleted} shows.")
