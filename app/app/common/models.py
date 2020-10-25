import datetime
from functools import wraps
import json
import logging
import math
import os
import subprocess

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import models
from django.db.transaction import on_commit
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils import timezone

from constance import config


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

    modified = models.DateTimeField('last modified', auto_now=True)
    email = models.EmailField('email address', unique=True)
    harbor_auth = models.CharField('harbor access type', max_length=1,
                                   choices=HarborAuth.choices, default=HarborAuth.ALWAYS)
    google_calender_entry_grace_minutes = models.PositiveIntegerField(
        'harbor entry grace period (minutes)', default=0, help_text=mark_safe(
            'The minutes <strong>before</strong> a scheduled show that the user is allowed to enter the harbor.'))
    google_calender_exit_grace_minutes = models.PositiveIntegerField(
        'harbor exit grace period (minutes)', default=0, help_text=mark_safe(
            'The minutes <strong>after</strong> a scheduled show that the user is kicked off the harbor.'))

    def get_full_name(self):
        s = ' '.join(filter(None, (self.first_name, self.last_name))).strip()
        return s if s else self.username

    @cached_property
    def show_times(self):
        try:
            return self._show_times.show_times
        except User._show_times.RelatedObjectDoesNotExist:
            return []

    def currently_harbor_authorized(self, now=None):
        auth_log = f'harbor_auth = {self.get_harbor_auth_display()}'

        if self.harbor_auth == self.HarborAuth.ALWAYS:
            logger.info(f'auth requested by {self}: allowed ({auth_log})')
            return True

        elif self.harbor_auth == self.HarborAuth.GOOGLE_CALENDAR:
            if config.GOOGLE_CALENDAR_ENABLED:
                show_times = self.get_show_times()

                if show_times:
                    if now is None:
                        now = timezone.now()
                    entry_grace = datetime.timedelta(minutes=self.google_calender_entry_grace_minutes)
                    exit_grace = datetime.timedelta(minutes=self.google_calender_exit_grace_minutes)
                    for show_time in show_times:
                        if (show_time.lower - entry_grace) <= now <= (show_time.upper + exit_grace):
                            logger.info(f'auth requested by {self}: allowed ({auth_log} and {now} in time bounds - '
                                        f'{timezone.localtime(show_time.lower)} [{entry_grace} entry grace] - '
                                        f'{timezone.localtime(show_time.upper)} [{exit_grace} exit grace])')
                            return True
                    else:
                        logger.info(f'auth requested by {self}: denied ({auth_log} with {now} not in time bounds for '
                                    f'{len(google_calendar_show_times.show_times)} show times)')
                        return False
                else:
                    logger.info(f'auth requested by {self}: denied ({auth_log} with no show times)')
                    return False
            else:
                logger.info(f'auth requested by {self}: allowed ({auth_log}, however GOOGLE_CALENDAR_ENABLED = False, '
                            f'so treating this like harbor_auth = {self.HarborAuth.ALWAYS.label})')
                return True
        else:
            logger.info(f'auth requested by {self}: denied ({auth_log})')
            return False


class AudioAssetBase(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = '-', 'upload pending'
        UPLOADED = 'u', 'uploaded'
        QUEUED = 'q', 'download queued'
        RUNNING = 'r', 'download running'
        FAILED = 'f', 'download failed'

    title = TruncatingCharField('title', max_length=255, blank=True,
                                help_text="If left empty, a title will be generated from the file's metadata.")
    # TODO these are for the playout audio assets
    # artist = TruncatingCharField('artist', max_length=255, blank=True,
    #                              help_text="If left empty, an artist will be generated from the file's metadata.")
    # album = TruncatingCharField('album', max_length=255, blank=True,
    #                             help_text="If left empty, an album will be generated from the file's metadata.")
    uploader = models.ForeignKey(User, verbose_name='uploader', on_delete=models.SET_NULL, null=True)
    file = models.FileField('audio file', upload_to='prerecord/', blank=True,
                            help_text='You can provide either an uploaded audio file or a URL to an external asset.')
    duration = models.DurationField('Audio duration', default=datetime.timedelta(0))
    status = models.CharField('Upload status', max_length=1, choices=Status.choices, default=Status.PENDING)
    task_id = models.UUIDField(null=True)

    class Meta:
        abstract = True

    @cached_property
    def task_log_line(self):
        # TODO clean up a bit, here and in BroadcastAssetAdmin.get_fields()
        # This is cached for the lifetime of the object so it isn't read twice with different values
        # by admin
        if self.status == self.Status.RUNNING:
            return cache.get(f'ydl-log:{self.task_id}')

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
    def queue_download(self, url, set_title=''):
        from .tasks import asset_download_external_url

        task = asset_download_external_url(self, url, title=set_title)
        model_cls = type(self)
        model_cls.objects.filter(id=self.id).update(task_id=task.id)
        model_cls.objects.filter(id=self.id, status=model_cls.Status.PENDING).update(status=model_cls.Status.QUEUED)

    def __str__(self):
        # TODO: work with album + artist
        # ' - '.join(filter(None, (getattr(self, 'artist', None), getattr(self, 'album', None), self.title)))
        title = self.title
        if self.duration != datetime.timedelta(0):
            title = f'{title} [{self.duration}]'
        return title
