import datetime
from functools import wraps
import json
import logging
import math
import os
import subprocess

import pytz

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import models
from django.db.transaction import on_commit
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils import timezone

from constance import config

from carb import constants


logger = logging.getLogger(f'carb.{__name__}')


def after_db_commit(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        on_commit(lambda: func(*args, **kwargs))
    return wrapped


class TruncatingCharField(models.CharField):
    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value:
            return value[:self.max_length]
        return value


class TimestampedModel(models.Model):
    created = models.DateTimeField('created', auto_now_add=True)
    modified = models.DateTimeField('last modified', auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    class HarborAuth(models.TextChoices):
        ALWAYS = 'a', 'always allowed'
        NEVER = 'n', 'never allowed'
        GOOGLE_CALENDAR = 'g', 'Google Calendar based'

    is_staff = True  # All users can access admin site.
    modified = models.DateTimeField('last modified', auto_now=True)
    email = models.EmailField('email address', unique=True)
    harbor_auth = models.CharField('harbor access type', max_length=1,
                                   choices=HarborAuth.choices, default=HarborAuth.ALWAYS)
    timezone = models.CharField('timezone', choices=[
        (tz, tz.replace('_', ' ')) for tz in pytz.common_timezones], max_length=60, default=settings.TIME_ZONE)
    google_calender_entry_grace_minutes = models.PositiveIntegerField(
        'harbor entry grace period (minutes)', default=0, help_text=mark_safe(
            'The minutes <strong>before</strong> a scheduled show that the user is allowed to enter the harbor.'))
    google_calender_exit_grace_minutes = models.PositiveIntegerField(
        'harbor exit grace period (minutes)', default=0, help_text=mark_safe(
            'The minutes <strong>after</strong> a scheduled show that the user is kicked off the harbor.'))

    def __init__(self, *args, **kwargs):
        if 'is_staff' in kwargs:
            del kwargs['is_staff']
        super().__init__(*args, **kwargs)

    def get_full_name(self):
        s = ' '.join(filter(None, (self.first_name, self.last_name))).strip()
        return s or self.username

    def harbor_auth_actual(self):
        if self.harbor_auth == User.HarborAuth.GOOGLE_CALENDAR and not config.GOOGLE_CALENDAR_ENABLED:
            return User.HarborAuth.ALWAYS
        else:
            return self.harbor_auth

    def harbor_auth_pretty(self):
        if self.harbor_auth == User.HarborAuth.GOOGLE_CALENDAR:
            if config.GOOGLE_CALENDAR_ENABLED:
                return (f'{self.get_harbor_auth_display()} ({self.google_calender_entry_grace_minutes} mins early '
                        f'entry, {self.google_calender_exit_grace_minutes} mins late exit)')
            else:
                return User.HarborAuth.ALWAYS.label
        else:
            return self.get_harbor_auth_display()
    harbor_auth_pretty.short_description = harbor_auth.verbose_name
    harbor_auth_pretty.admin_order_field = 'harbor_auth'

    @cached_property
    def show_times(self):
        try:
            return self._show_times.show_times
        except User._show_times.RelatedObjectDoesNotExist:
            return []

    @cached_property
    def upcoming_show_times(self):
        now = timezone.now()
        entry_grace = datetime.timedelta(minutes=self.google_calender_entry_grace_minutes)
        exit_grace = datetime.timedelta(minutes=self.google_calender_exit_grace_minutes)

        upcoming_show_times = []
        for show_time in self.show_times:
            # Current show
            if (show_time.lower - entry_grace) <= now <= (show_time.upper + exit_grace):
                upcoming_show_times.append(show_time)
            # And future shows
            elif show_time.lower > now:
                upcoming_show_times.append(show_time)
        return upcoming_show_times

    def currently_harbor_authorized(self, now=None, should_log=True):
        auth_log = f'harbor_auth = {self.get_harbor_auth_display()}'
        ban_seconds = cache.ttl(f'{constants.CACHE_KEY_HARBOR_BAN_PREFIX}{self.id}')

        def log(s):
            if should_log:
                logger.info(s)

        if ban_seconds > 0:
            log(f'auth requested by {self}: denied ({auth_log}, but BANNED with {ban_seconds} seconds left)')
            return False

        elif self.harbor_auth == self.HarborAuth.ALWAYS:
            log(f'auth requested by {self}: allowed ({auth_log})')
            return True

        elif self.harbor_auth == self.HarborAuth.GOOGLE_CALENDAR:
            if config.GOOGLE_CALENDAR_ENABLED:
                if self.show_times:
                    if now is None:
                        now = timezone.now()
                    entry_grace = datetime.timedelta(minutes=self.google_calender_entry_grace_minutes)
                    exit_grace = datetime.timedelta(minutes=self.google_calender_exit_grace_minutes)
                    for show_time in self.show_times:
                        upper_bound = show_time.upper + exit_grace
                        if (show_time.lower - entry_grace) <= now <= upper_bound:
                            log(f'auth requested by {self}: allowed ({auth_log} and {now} in time bounds - '
                                f'{timezone.localtime(show_time.lower)} [{entry_grace} entry grace] - '
                                f'{timezone.localtime(show_time.upper)} [{exit_grace} exit grace])')
                            return upper_bound
                    else:
                        log(f'auth requested by {self}: denied ({auth_log} with {now} not in time bounds for '
                            f'{len(self.show_times)} show times)')
                        return False
                else:
                    log(f'auth requested by {self}: denied ({auth_log} with no show times)')
                    return False
            else:
                log(f'auth requested by {self}: allowed ({auth_log}, however GOOGLE_CALENDAR_ENABLED = False, '
                    f'so treating this like harbor_auth = {self.HarborAuth.ALWAYS.label})')
                return True
        else:
            log(f'auth requested by {self}: denied ({auth_log})')
            return False


def audio_asset_file_upload_to(instance, filename):
    return f'{instance.UPLOAD_DIR}/{filename}'


class AudioAssetBase(TimestampedModel):
    UNNAMED_TRACK = 'Untitled Track'
    UPLOAD_DIR = 'assets'
    TITLE_FIELDS = ('title',)

    class Status(models.TextChoices):
        PENDING = '-', 'upload pending'
        UPLOADED = 'u', 'uploaded'
        QUEUED = 'q', 'download queued'
        RUNNING = 'r', 'download running'
        FAILED = 'f', 'download failed'

    title = TruncatingCharField('title', max_length=255, blank=True,
                                help_text="If left empty, a title will be generated from the file's metadata.")
    uploader = models.ForeignKey(User, verbose_name='uploader', on_delete=models.SET_NULL, null=True)
    file = models.FileField('audio file', blank=True, upload_to=audio_asset_file_upload_to,
                            help_text='You can provide either an uploaded audio file or a URL to an external asset.')
    duration = models.DurationField('Audio duration', default=datetime.timedelta(0))
    status = models.CharField('upload status', max_length=1, choices=Status.choices, default=Status.PENDING,
                              db_index=True)
    task_id = models.UUIDField(null=True)

    class Meta:
        abstract = True

    @cached_property
    def task_log_line(self):
        # TODO clean up a bit, here and in BroadcastAssetAdmin.get_fields()
        # This is cached for the lifetime of the object so it isn't read twice with different values
        # by admin
        if self.status == self.Status.RUNNING:
            return cache.get(f'{constants.CACHE_KEY_YTDL_TASK_LOG_PREFIX}{self.task_id}')

    @property
    def file_path(self):
        if isinstance(self.file.file, TemporaryUploadedFile):
            return self.file.file.temporary_file_path()
        else:
            return self.file.path

    def set_fields_from_exiftool(self):
        cmd = subprocess.run(['exiftool', '-json', self.file_path], capture_output=True)

        if cmd.returncode == 0:
            exif_data = json.loads(cmd.stdout)[0]
            fields = {field_name: exif_data.get(field_name.title(), '') for field_name in self.TITLE_FIELDS}
            # Special case if there's no artist field, update title to be "artist - title"
            if not fields['title'] and 'artist' not in self.TITLE_FIELDS:
                fields['title'] = ' - '.join(filter(None, (exif_data.get('Artist'), self.title)))

            for field_name, value in fields.items():
                if not getattr(self, field_name):
                    setattr(self, field_name, value)

        if not self.title:
            self.title = os.path.splitext(os.path.basename(self.file.name))[0].replace('_', ' ')

    def set_duration_from_ffprobe(self):
        cmd = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
                              'default=noprint_wrappers=1:nokey=1', self.file_path], capture_output=True)
        if cmd.returncode == 0:
            self.duration = datetime.timedelta(seconds=math.ceil(float(cmd.stdout.decode().strip())))

    def save(self, *args, **kwargs):
        if self.file:
            self.set_fields_from_exiftool()
            if self.duration == datetime.timedelta(0):
                self.set_duration_from_ffprobe()
            self.status = self.Status.UPLOADED
        super().save(*args, **kwargs)

    @after_db_commit
    def queue_download(self, url, set_title=''):
        from .tasks import asset_download_external_url

        task = asset_download_external_url(self, url, title=set_title)
        model_cls = type(self)
        model_cls.objects.filter(id=self.id).update(task_id=task.id)
        model_cls.objects.filter(id=self.id, status=model_cls.Status.PENDING).update(status=model_cls.Status.QUEUED)
        cache.set(f'{constants.CACHE_KEY_YTDL_TASK_LOG_PREFIX}{task.id}', f'Starting download for {url}')

    def __str__(self, s=None):
        if s is None:
            s = self.title
        if not s:
            s = self.UNNAMED_TRACK
        if self.duration != datetime.timedelta(0):
            s = f'{s} [{self.duration}]'
        return s
