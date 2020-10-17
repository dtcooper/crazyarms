import datetime
import json

from dateutil.parser import parse as parse
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from django.contrib.auth.models import User
from django.db import models
from django.db.transaction import on_commit as django_on_commit
from django.utils.timezone import localtime, make_aware

from constance import config
from huey.contrib.djhuey import revoke_by_id


HARBOR_AUTH_ALWAYS = 'a'
HARBOR_AUTH_NEVER = 'n'
HARBOR_AUTH_SCHEDULE = 's'
HARBOR_AUTH_CHOICES = (
    (HARBOR_AUTH_ALWAYS, 'Always'),
    (HARBOR_AUTH_NEVER, 'Never'),
    (HARBOR_AUTH_SCHEDULE, 'Schedule Based'),
)

PLAY_STATUS_NEWLY_CREATED = 'n'
PLAY_STATUS_QUEUED = 'q'
PLAY_STATUS_PLAYED = 'p'
PLAY_STATUS_ERROR = 'e'
PLAY_STATUS_CHOICES = (
    (PLAY_STATUS_NEWLY_CREATED, 'Newly Created'),
    (PLAY_STATUS_QUEUED, 'Queued'),
    (PLAY_STATUS_PLAYED, 'Played'),
    (PLAY_STATUS_ERROR, 'Error'),
)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    harbor_auth = models.CharField(max_length=1, choices=HARBOR_AUTH_CHOICES)
    early_entry = models.DurationField()

    def __str__(self):
        if self.user is None:
            return 'New user profile'
        else:
            return f'Profile for {self.user.get_full_name()}'


class GoogleCalendarShow(models.Model):
    uid = models.CharField(max_length=1024, unique=True)
    title = models.CharField('Title', max_length=1024)
    start = models.DateTimeField('Start Time')
    end = models.DateTimeField('End Time')
    users = models.ManyToManyField(User, verbose_name='Authorized Users')

    def __str__(self):
        return f'{self.title} - {localtime(self.start)} to {localtime(self.end)}'

    class Meta:
        verbose_name = 'Google Calendar Show'
        verbose_name_plural = 'Google Calendar Shows'

    @classmethod
    def create_or_update_from_api_item(cls, item, email_to_user_cache=None):
        emails = {attendee['email'] for attendee in item.get('attendees', [])}
        creator = item.get('creator', {}).get('email')
        if creator is not None:
            emails.add(creator)

        defaults = {
            'title': item.get('summary', 'Untitled Show'),
            # Start time / end time, server time if full day event
            'start': (make_aware(parse(item['start']['date']), is_dst=False)
                      if item['start'].get('dateTime') is None else parse(item['start'].get('dateTime'))),
            'end': (make_aware(parse(item['end']['date']).replace(hour=23, minute=59, second=59), is_dst=True)
                    if item['end'].get('dateTime') is None else parse(item['end'].get('dateTime'))),
        }

        obj, created = cls.objects.update_or_create(
            uid=item['id'],
            defaults=defaults,
        )

        allowed_users = set()
        for email in emails:
            cached_user = None if email_to_user_cache is None else email_to_user_cache.get(email)
            if cached_user is None:
                try:
                    user = email_to_user_cache[email] = User.objects.get(email=email)
                except User.DoesNotExist:
                    user = email_to_user_cache[email] = False
            else:
                user = email_to_user_cache[email]

            if user:
                allowed_users.add(user)
                obj.users.add(user)

        for user in obj.users.all():
            if user not in allowed_users:
                obj.users.remove(user)

        return obj

    @classmethod
    def sync_api(cls):
        credentials = Credentials.from_service_account_info(json.loads(config.GOOGLE_CALENDAR_CREDENTIALS_JSON))
        service = build('calendar', 'v3', credentials=credentials)

        seen_uids = set()
        email_to_user_cache = {}

        page_token = None
        while True:
            response = service.events().list(
                calendarId=config.GOOGLE_CALENDAR_ID,
                maxResults=2500,
                timeMin=(datetime.datetime.utcnow() - datetime.timedelta(days=60)).isoformat() + 'Z',
                timeMax=(datetime.datetime.utcnow() + datetime.timedelta(days=120)).isoformat() + 'Z',
                timeZone='UTC',
                singleEvents='true',
                pageToken=page_token,
            ).execute()

            for item in response['items']:
                obj = cls.create_or_update_from_api_item(item, email_to_user_cache=email_to_user_cache)
                seen_uids.add(obj.uid)

            page_token = response.get('nextPageToken')
            if page_token is None:
                break

        cls.objects.exclude(uid__in=seen_uids).delete()


class ScheduledBroadcast(models.Model):
    asset_path = models.CharField(max_length=1024)
    scheduled_time = models.DateTimeField()
    task_id = models.UUIDField(null=True)
    play_status = models.CharField(max_length=1, choices=PLAY_STATUS_CHOICES, default=PLAY_STATUS_NEWLY_CREATED)

    def __str__(self):
        return f'{self.asset_path} @ {localtime(self.scheduled_time)} [{self.get_play_status_display()}]'

    class Meta:
        ordering = ('-scheduled_time',)

    def queue(self, on_commit=True):
        if on_commit:
            django_on_commit(lambda: self.queue(on_commit=False))
        else:
            from .tasks import play_scheduled_broadcast

            task = play_scheduled_broadcast.schedule(args=(self.id,), eta=self.scheduled_time)
            ScheduledBroadcast.objects.filter(id=self.id).update(task_id=task.id)
            # Only update the status to queued if it's still NEWLY_CREATED -- so we don't thrash with
            # task if it's already updated the status
            ScheduledBroadcast.objects.filter(id=self.id, play_status=PLAY_STATUS_NEWLY_CREATED).update(
                play_status=PLAY_STATUS_QUEUED)

    def delete(self, *args, **kwargs):
        if self.task_id:
            revoke_by_id(self.task_id)
        return super().delete(*args, **kwargs)
