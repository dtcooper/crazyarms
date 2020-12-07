from collections import namedtuple
import datetime
from functools import wraps
import json
import logging
import math
import os
import random
import string
import subprocess
import uuid

import pytz
import unidecode

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group
from django.core.cache import cache
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import models
from django.db.transaction import on_commit
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone

from constance import config
from dirtyfields import DirtyFieldsMixin

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
    email = models.EmailField('email address', unique=True, help_text='This is needed to match Google Calendar events '
                                                                      'for calendar based harbor authorization.')
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
    groups = models.ManyToManyField(
        Group, verbose_name='permissions', blank=True, related_name='user_set', related_query_name='user')

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


def normalize_title_field(value):
    return (' '.join(unidecode.unidecode(value).strip().split())).lower()


def audio_asset_file_upload_to(instance, filename):
    return f'{instance.UPLOAD_DIR}/{filename}'


FFProbe = namedtuple('FFProbe', ('format', 'duration', 'artist', 'album', 'title'))


class AudioAssetBase(DirtyFieldsMixin, TimestampedModel):
    UNNAMED_TRACK = 'Untitled Track'
    UPLOAD_DIR = 'assets'
    TITLE_FIELDS = ('title',)
    FFMPEG_ACCEPTABLE_FORMATS = ('mp3', 'ogg', 'flac')

    title = TruncatingCharField('title', max_length=255, blank=True, db_index=True,
                                help_text="If left empty, a title will be generated from the file's metadata.")
    uploader = models.ForeignKey(User, verbose_name='uploader', on_delete=models.SET_NULL, null=True)
    file = models.FileField('audio file', max_length=512, upload_to=audio_asset_file_upload_to)
    duration = models.DurationField('Audio duration', default=datetime.timedelta(0))
    fingerprint = models.UUIDField(null=True, db_index=True)  # 32 byte md5 = a UUID

    def __init__(self, *args, **kwargs):
        self.pre_convert_filename = kwargs.pop('pre_convert_filename', None)
        super().__init__(*args, **kwargs)

    class Meta:
        abstract = True
        ordering = ('title', 'id')

    def audio_player_html(self):
        if self.file:
            return format_html('<audio src="{}" style="width: 100%" preload="auto" controls />', self.file.url)
        return mark_safe('<em>None</em>')
    audio_player_html.short_description = 'Audio'

    @property
    def file_path(self):
        if self.file:
            if isinstance(self.file.file, TemporaryUploadedFile):
                return self.file.file.temporary_file_path()
            else:
                return self.file.path

    def clear_ffprobe_cache(self):
        try:
            del self.ffprobe
        except AttributeError:
            pass

    def set_fields_from_ffprobe(self):
        # TODO: switch back to exiftool due to apparent id3v2.4 bug in ffmpeg @ https://superuser.com/q/1282809

        for field_name in self.TITLE_FIELDS:
            if not getattr(self, field_name):
                setattr(self, field_name, getattr(self.ffprobe, field_name) or '')

        # Special case if there's no artist field, update title to be "artist - title"
        if self.title and 'artist' not in self.TITLE_FIELDS:
            self.title = ' - '.join(filter(None, (self.ffprobe.artist, self.ffprobe.title)))

        if not self.title:
            logger.warning('ffprobe returned an empty title. Setting title from file name.')
            self.title = os.path.splitext(os.path.basename(
                self.pre_convert_filename or self.file.name))[0].replace('_', ' ')

    @cached_property
    def ffprobe(self):
        if self.file:
            cmd = subprocess.run(['ffprobe', '-i', self.file_path, '-print_format', 'json', '-hide_banner', '-loglevel',
                                  'error', '-show_format', '-show_error', '-show_streams', '-select_streams', 'a:0'],
                                 text=True, capture_output=True)
            if cmd.returncode == 0:
                data = json.loads(cmd.stdout)
                if data:
                    if data['streams'] and data['format']:
                        tags = data['format'].get('tags', {})
                        return FFProbe(
                            artist=tags.get('artist'), album=tags.get('album'), title=tags.get('title'),
                            format=data['format']['format_name'], duration=datetime.timedelta(
                                seconds=math.ceil(float(data['streams'][0].get('duration') or 0))),
                        )

                logger.warning(f'ffprobe returned a bad or empty response: {cmd.stdout}')
            else:
                logger.warning(f'ffprobe returned {cmd.returncode}: {cmd.stderr}')

    def convert_to_acceptable_format(self, pre_save_delete=True):
        new_ext = config.ASSET_ENCODING
        if new_ext == 'vorbis':
            new_ext = 'ogg'

        self.pre_convert_filename = self.file.name
        outfile = os.path.splitext(
            f'{settings.MEDIA_ROOT}converted/{audio_asset_file_upload_to(self, self.file.name)}')[0]
        if os.path.exists(f'{outfile}.{new_ext}'):
            outfile += '_' + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(7))
        outfile += f'.{new_ext}'
        os.makedirs(os.path.dirname(outfile), exist_ok=True)

        cmd_args = ['ffmpeg', '-v', 'error', '-y', '-i', self.file_path, '-map', '0:a:0']
        if config.ASSET_ENCODING != 'flac':
            cmd_args.extend(['-b:a', config.ASSET_BITRATE.lower()])
        cmd_args.extend(['--', outfile])

        cmd = subprocess.run(cmd_args, text=True, capture_output=True)
        if cmd.returncode == 0 and os.path.exists(outfile):
            logger.info(f'ffmpeg removed {self.file_path} and converted to {outfile}. ')
            if pre_save_delete:
                self.file.delete(save=False)
            self.file = outfile.removeprefix(settings.MEDIA_ROOT)
        else:
            logger.warning(
                f"ffmpeg (conversion) returned {cmd.returncode} (or converted {outfile} doesn't exist): {cmd.stderr}")
            if pre_save_delete:
                self.file.delete(save=False)
            self.file = None
        self.clear_ffprobe_cache()

    @cached_property
    def computed_fingerprint(self):
        cmd = subprocess.run(['ffmpeg', '-v', 'error',  '-i', self.file_path, '-map', '0:a:0', '-f', 'md5', '-'],
                             text=True, capture_output=True)
        if cmd.returncode == 0 and cmd.stdout.startswith('MD5='):
            return uuid.UUID(cmd.stdout.removeprefix('MD5=').strip())
        else:
            logger.warning(f'ffmpeg (md5) return {cmd.returncode}: {cmd.stderr}')
            return None

    def clean(self):
        if self.file:
            if not self.ffprobe:
                raise ValidationError("Failed to extract audio info from the file you've uploaded. Try another?")

            if self.computed_fingerprint:
                match = self._meta.model.objects.exclude(id=self.id).filter(
                    fingerprint=self.computed_fingerprint).first()
                if match:
                    raise ValidationError(f'A track already exists with the same audio content: {match}')

    def pre_save(self, pre_save_delete=True):
        # We don't allow files that are unrecognized by ffprobe. Shouldn't happen because of clean()
        if not (self.ffprobe and os.path.exists(self.file_path)):
            if self.file and pre_save_delete:
                self.file.delete(save=False)
            self.file = None

        if self.file:
            if 'file' in self.get_dirty_fields():
                if not self.fingerprint:
                    self.fingerprint = self.computed_fingerprint  # Pre-conversion to acceptable format

                if self.ffprobe.format not in self.FFMPEG_ACCEPTABLE_FORMATS:
                    self.convert_to_acceptable_format(pre_save_delete=pre_save_delete)

                if self.file:  # convert_to_acceptable_format() may have set self.file = None
                    self.duration = self.ffprobe.duration

            if self.file:  # convert_to_acceptable_format() may have set self.file = None
                if not any(getattr(self, field) for field in self.TITLE_FIELDS):
                    self.set_fields_from_ffprobe()

                if isinstance(self, AudioAssetDownloadbleBase):
                    self.status = self.Status.UPLOADED
        else:
            self.file = self.fingerprint = None
            self.duration = datetime.timedelta(0)

        if not self.title:
            self.title = self.UNNAMED_TRACK

        # re-normalize title fields before save
        for field_name in self.TITLE_FIELDS:
            try:
                self._meta.get_field(f'{field_name}_normalized')
            except FieldDoesNotExist:
                pass
            else:
                value = getattr(self, field_name)
                normalized_field_name = f'{field_name}_normalized'
                if field_name in self.get_dirty_fields() or (value and not getattr(self, normalized_field_name)):
                    setattr(self, normalized_field_name, normalize_title_field(value))

    def save(self, run_pre_save=True, pre_save_delete=True, *args, **kwargs):
        if run_pre_save:
            self.pre_save(pre_save_delete=pre_save_delete)
        super().save(*args, **kwargs)

    def __str__(self, s=None):
        if s is None:
            s = self.title
        if not s:
            s = self.UNNAMED_TRACK
        if self.duration != datetime.timedelta(0):
            s = f'{s} [{self.duration}]'
        return s


class AudioAssetDownloadbleBase(AudioAssetBase):
    class Status(models.TextChoices):
        PENDING = '-', 'upload pending'
        UPLOADED = 'u', 'uploaded'
        QUEUED = 'q', 'download queued'
        RUNNING = 'r', 'download running'
        FAILED = 'f', 'download failed'
    # Changes to blank=True + help_text
    file = models.FileField('audio file', max_length=512, blank=True, upload_to=audio_asset_file_upload_to,
                            help_text='You can provide either an uploaded audio file or a URL to an external asset.')
    status = models.CharField('upload status', max_length=1, choices=Status.choices,
                              default=Status.PENDING, db_index=True)
    task_id = models.UUIDField(null=True)

    class Meta:
        abstract = True

    @after_db_commit
    def queue_download(self, url, set_title=''):
        from .tasks import asset_download_external_url

        task = asset_download_external_url(self, url, title=set_title)
        model_cls = self._meta.model
        model_cls.objects.filter(id=self.id).update(task_id=task.id)
        model_cls.objects.filter(id=self.id, status=model_cls.Status.PENDING).update(status=model_cls.Status.QUEUED)
        cache.set(f'{constants.CACHE_KEY_YTDL_TASK_LOG_PREFIX}{task.id}', f'Starting download for {url}')

    @cached_property
    def task_log_line(self):
        # TODO clean up a bit, here and in BroadcastAssetAdmin.get_fields()
        # This is property cached for the lifetime of the object so it isn't read twice with
        # different values by admin
        if self.status == self.Status.RUNNING:
            return cache.get(f'{constants.CACHE_KEY_YTDL_TASK_LOG_PREFIX}{self.task_id}')
