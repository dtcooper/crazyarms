import datetime
from functools import wraps
import json
import math
import os
import subprocess

from dateutil.parser import parse as parse
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from django.contrib.auth.models import AbstractUser
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import models
from django.db.transaction import on_commit
from django.utils.timezone import localtime, make_aware

from constance import config
from huey.contrib.djhuey import revoke_by_id


def after_db_commit(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        print(args, kwargs)
        on_commit(lambda: func(*args, **kwargs))
    return wrapped


class TruncatingCharField(models.CharField):
    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value:
            return value[:self.max_length]
        return value


class User(AbstractUser):
    class HarborAuth(models.TextChoices):
        ALWAYS = 'a', 'Always'
        NEVER = 'n', 'Never'
        GOOGLE_CALENDAR = 'g', 'Google Calendar based'

    email = models.EmailField('Email address', unique=True)
    harbor_auth = models.CharField('Harbor access type', max_length=1,
                                   choices=HarborAuth.choices, default=HarborAuth.ALWAYS)


class GoogleCalendarShow(models.Model):
    uid = TruncatingCharField(max_length=1024, unique=True)
    title = TruncatingCharField('Title', max_length=255)
    start = models.DateTimeField('Start time')
    end = models.DateTimeField('End time')
    users = models.ManyToManyField(User, verbose_name='Authorized users')

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


class AudioAssetBase(models.Model):
    class FileStatus(models.TextChoices):
        PENDING = '-', 'Upload pending'
        UPLOADED = 'u', 'Uploaded'
        QUEUED = 'q', 'Download queued'
        RUNNING = 'r', 'Download running'
        FAILED = 'f', 'Download failed'

    title = TruncatingCharField('Title', max_length=255, blank=True,
                                help_text="If left empty, a title will be generated from the file's metadata.")
    uploader = models.ForeignKey(User, verbose_name='Uploader', on_delete=models.SET_NULL, null=True)
    file = models.FileField('Audio file', upload_to='prerecord/', blank=True,
                            help_text="You can provide either an uploaded audio file or a URL to an external asset.")
    duration = models.DurationField('Audio duration', default=datetime.timedelta(0))
    file_status = models.CharField('Upload status', max_length=1,
                                   choices=FileStatus.choices, default=FileStatus.PENDING)
    task_id = models.UUIDField(null=True)

    @property
    def file_path(self):
        if isinstance(self.file.file, TemporaryUploadedFile):
            return self.file.file.temporary_file_path()
        else:
            return self.file.path

    def set_title_from_exiftool(self):
        title = None
        cmd = subprocess.run(['exiftool', '-json', self.file_path], capture_output=True)
        if cmd.returncode == 0:
            exif = json.loads(cmd.stdout)[0]
            title = ' - '.join(filter(None, (exif.get('Artist'), exif.get('Title'))))

        if not title:
            title = os.path.splitext(os.path.basename(self.file.name))[0].replace('_', ' ')

        self.title = title

    def set_duration_from_ffprobe(self):
        cmd = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
                              'default=noprint_wrappers=1:nokey=1', self.file_path], capture_output=True)
        if cmd.returncode == 0:
            self.duration = datetime.timedelta(seconds=math.ceil(float(cmd.stdout.decode().strip())))

    def save(self, *args, **kwargs):
        if self.file:
            if not self.title:
                self.set_title_from_exiftool()
            if self.duration == datetime.timedelta(0):
                self.set_duration_from_ffprobe()
        super().save(*args, **kwargs)

    @after_db_commit
    def queue_download(self, url, title=None):
        from .tasks import download_external_url

        model_cls = self.__class__
        task = download_external_url(model_cls, self.id, url, title)
        model_cls.objects.filter(id=self.id).update(task_id=task.id)
        model_cls.objects.filter(id=self.id, file_status=AudioAssetBase.FileStatus.PENDING).update(
            file_status=AudioAssetBase.FileStatus.QUEUED)

    class Meta:
        abstract = True

    def __str__(self):
        title = ' - '.join(filter(None, (getattr(self, 'artist', None), getattr(self, 'album', None), self.title)))
        if self.duration != datetime.timedelta(0):
            title = f'{title} [{self.duration}]'
        return title


class AudioAsset(AudioAssetBase):
    artist = TruncatingCharField('Artist', max_length=255, blank=True,
                                 help_text="If left empty, an artist will be generated from the file's metadata.")
    album = TruncatingCharField('Album', max_length=255, blank=True,
                                help_text="If left empty, an album will be generated from the file's metadata.")

    class Meta:
        verbose_name = 'Playout Audio Asset'
        verbose_name_plural = 'Playout Audio Assets'


class PrerecordedAsset(AudioAssetBase):
    class Meta:
        verbose_name = 'Prerecorded Broadcast Audio Asset'
        verbose_name_plural = 'Prerecorded Broadcast Audio Assets'


class PrerecordedBroadcast(models.Model):
    class PlayStatus(models.TextChoices):
        PENDING = '-', 'Pending'
        QUEUED = 'q', 'Queued'
        PLAYED = 'p', 'Played'
        FAILED = 'f', 'Queuing failed'

    asset = models.ForeignKey(PrerecordedAsset, verbose_name='Audio file', on_delete=models.CASCADE)
    scheduled_time = models.DateTimeField()
    task_id = models.UUIDField(null=True)
    play_status = models.CharField(max_length=1, choices=PlayStatus.choices, default=PlayStatus.PENDING)

    def __str__(self):
        return f'{self.asset} @ {localtime(self.scheduled_time)} [{self.get_play_status_display()}]'

    class Meta:
        ordering = ('-scheduled_time',)
        verbose_name = 'Prerecorded Broadcast'
        verbose_name_plural = 'Prerecorded Broadcasts'

    @after_db_commit
    def queue(self):
        from .tasks import play_prerecorded_broadcast

        task = play_prerecorded_broadcast.schedule(args=(self.id,), eta=self.scheduled_time)
        PrerecordedBroadcast.objects.filter(id=self.id).update(task_id=task.id)
        # Only update the status to queued if it's still PENDING -- so we don't thrash with
        # task if it's already updated the status
        PrerecordedBroadcast.objects.filter(id=self.id, play_status=PrerecordedBroadcast.PlayStatus.PENDING).update(
            play_status=PrerecordedBroadcast.PlayStatus.QUEUED)

    def delete(self, *args, **kwargs):
        if self.task_id:
            revoke_by_id(self.task_id)
        return super().delete(*args, **kwargs)
