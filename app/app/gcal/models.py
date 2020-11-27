from collections import defaultdict
import datetime
import json
import logging

from dateutil.parser import parse as parse
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from django.contrib.postgres.fields import ArrayField, DateTimeRangeField
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from constance import config

from carb import constants
from common.models import TimestampedModel, User


logger = logging.getLogger(f'carb.{__name__}')


class GoogleCalendarShowTimes(TimestampedModel):
    # TODO: This could be a arrayfield on User and we could scrape the gcal module
    #     - sync code could be a task

    SYNC_RANGE_DAYS_MIN = datetime.timedelta(days=60)
    SYNC_RANGE_DAYS_MAX = datetime.timedelta(days=120)

    user = models.OneToOneField(User, db_index=True, on_delete=models.CASCADE, related_name='_show_times')
    show_times = ArrayField(DateTimeRangeField())

    def __str__(self):
        return f'{self.user} ({len(self.show_times)} shows)'

    class Meta:
        order_with_respect_to = 'user'
        verbose_name = 'Google Calendar shows'
        verbose_name_plural = 'Google Calendar shows'

    @classmethod
    def get_last_sync(self):
        return cache.get(constants.CACHE_KEY_GCAL_LAST_SYNC)

    @classmethod
    def sync_api(cls):
        credentials = Credentials.from_service_account_info(json.loads(config.GOOGLE_CALENDAR_CREDENTIALS_JSON))
        service = build('calendar', 'v3', credentials=credentials)

        email_to_user = {}
        user_to_show_times = defaultdict(set)

        page_token = None
        while True:
            response = service.events().list(
                calendarId=config.GOOGLE_CALENDAR_ID,
                maxResults=2500,
                timeMin=(datetime.datetime.utcnow() - cls.SYNC_RANGE_DAYS_MIN).isoformat() + 'Z',
                timeMax=(datetime.datetime.utcnow() + cls.SYNC_RANGE_DAYS_MAX).isoformat() + 'Z',
                timeZone='UTC',
                singleEvents='true',
                pageToken=page_token,
            ).execute()

            for item in response['items']:
                start = (
                    timezone.make_aware(parse(item['start']['date']), is_dst=False)
                    if item['start'].get('dateTime') is None else parse(item['start'].get('dateTime'))
                )
                end = (
                    timezone.make_aware(parse(item['end']['date']).replace(hour=23, minute=59, second=59), is_dst=True)
                    if item['end'].get('dateTime') is None else parse(item['end'].get('dateTime'))
                )

                emails = [attendee['email'] for attendee in item.get('attendees', [])]
                creator = item.get('creator', {}).get('email')
                if creator is not None:
                    emails.append(creator)

                for email in emails:
                    user = email_to_user.get(email)
                    if not user:
                        try:
                            user = email_to_user[email] = User.objects.get(email=email)
                        except User.DoesNotExist:
                            pass

                    if user:
                        user_to_show_times[user].add((start, end))

            page_token = response.get('nextPageToken')
            if page_token is None:
                break

        for user, show_times in user_to_show_times.items():
            cls.objects.update_or_create(user=user, defaults={'show_times': sorted(show_times)})

        cls.objects.exclude(user__in=list(user_to_show_times.keys())).delete()
