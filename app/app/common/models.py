from collections import namedtuple
import datetime
from functools import wraps
import json
import logging
import math
import os
import secrets
import string
import subprocess
import uuid

import pytz

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group
from django.core.cache import cache
from django.core.exceptions import ValidationError
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


def generate_random_string(length):
    # Needs to be non-urlencodable (just alphanum characters) for nginx-rtmp to work without escaping hell
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))


def filter_inactive_group_queryset(queryset):
    for setting, perm_codename in (
        (settings.ZOOM_ENABLED, 'view_websockify'),
        (settings.HARBOR_TELNET_WEB_ENABLED, 'view_telnet'),
        (config.AUTODJ_ENABLED, 'change_audioasset'),
    ):
        if not setting:
            queryset = queryset.exclude(permissions__codename=perm_codename)
    return queryset


class User(DirtyFieldsMixin, AbstractUser):
    STREAM_KEY_LENGTH = 80

    class HarborAuth(models.TextChoices):
        ALWAYS = 'a', 'always allowed'
        NEVER = 'n', 'never allowed'
        GOOGLE_CALENDAR = 'g', 'Google Calendar based'

    is_staff = True  # All users can access admin site if they've got at least one permission
    is_superuser = models.BooleanField('administrator', default=False, help_text=mark_safe(
        'Designates that this user has <strong><u>all permissions</u></strong> without explicitly assigning them.'))
    modified = models.DateTimeField('last modified', auto_now=True)
    email = models.EmailField('email address', unique=True, help_text='This is needed to match Google Calendar events '
                                                                      'for calendar based harbor authorization.')
    harbor_auth = models.CharField('harbor access type', max_length=1,
                                   choices=HarborAuth.choices, default=HarborAuth.ALWAYS)
    timezone = models.CharField('timezone', choices=[
        (tz, tz.replace('_', ' ')) for tz in pytz.common_timezones], max_length=60, default=settings.TIME_ZONE)
    authorized_keys = models.TextField('SSH authorized keys', blank=True, help_text='Authorized public SSH keys for '
                                                                                    'SFTP and SCP (one per line).')
    stream_key = models.CharField('RTMP stream key', max_length=STREAM_KEY_LENGTH, unique=True,
                                  help_text='Users can reset this by editing their Profile.')
    gcal_entry_grace_minutes = models.PositiveIntegerField(
        'harbor entry grace period (minutes)', default=0, help_text=mark_safe(
            'The minutes <strong>before</strong> a scheduled show that the user is allowed to enter the harbor.'))
    gcal_exit_grace_minutes = models.PositiveIntegerField(
        'harbor exit grace period (minutes)', default=0, help_text=mark_safe(
            'The minutes <strong>after</strong> a scheduled show that the user is kicked off the harbor.'))
    groups = models.ManyToManyField(
        Group, verbose_name='permissions', blank=True, related_name='user_set', related_query_name='user')
    default_playlist = models.ForeignKey(
        'autodj.Playlist', verbose_name='default playlist (SFTP)', on_delete=models.SET_NULL, default=None,
        null=True, blank=True, help_text='Optional default playlist for when you upload audio assets using SFTP.')

    def __init__(self, *args, **kwargs):
        if 'is_staff' in kwargs:
            del kwargs['is_staff']
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.stream_key is None or 'password' in self.get_dirty_fields():
            self.stream_key = generate_random_string(self.STREAM_KEY_LENGTH)
        super().save(*args, **kwargs)

    def get_full_name(self, short=False):
        full_name = ' '.join(filter(None, (self.first_name, self.last_name))).strip()
        if full_name:
            if short:
                return full_name
            else:
                return f'{self.username} ({full_name})'
        else:
            return self.username

    def harbor_auth_actual(self):
        if self.harbor_auth == User.HarborAuth.GOOGLE_CALENDAR and not config.GOOGLE_CALENDAR_ENABLED:
            return User.HarborAuth.ALWAYS
        else:
            return self.harbor_auth

    def harbor_auth_pretty(self):
        if self.harbor_auth == User.HarborAuth.GOOGLE_CALENDAR:
            if config.GOOGLE_CALENDAR_ENABLED:
                return (f'{self.get_harbor_auth_display()} ({self.gcal_entry_grace_minutes} mins early entry, '
                        f'{self.gcal_exit_grace_minutes} mins late exit)')
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
        entry_grace = datetime.timedelta(minutes=self.gcal_entry_grace_minutes)
        exit_grace = datetime.timedelta(minutes=self.gcal_exit_grace_minutes)

        upcoming_show_times = []
        for show_time in self.show_times:
            lower, upper = show_time
            # Current show
            if (lower - entry_grace) <= now <= (upper + exit_grace):
                upcoming_show_times.append(show_time)
            # And future shows
            elif lower > now:
                upcoming_show_times.append(show_time)
        return upcoming_show_times

    def has_autodj_request_permission(self):
        if config.AUTODJ_ENABLED:
            code = config.AUTODJ_REQUESTS
            if code == 'disabled':
                return False
            elif code == 'user':
                return True
            elif code == 'perm':
                return self.has_perm('autodj.change_audioasset')
            else:  # code == 'superuser'
                return self.is_superuser
        else:
            return False

    def get_sftp_allowable_models(self):
        # Avoid circular imports
        from autodj.models import AudioAsset, RotatorAsset
        from broadcast.models import BroadcastAsset

        perms = []
        if config.AUTODJ_ENABLED and self.has_perm('autodj.change_audioasset'):
            perms.append(AudioAsset)
            if config.AUTODJ_STOPSETS_ENABLED:
                perms.append(RotatorAsset)
        if self.has_perm('broadcast.change_broadcast'):
            perms.append(BroadcastAsset)

        return perms

    def currently_harbor_authorized(self, now=None, should_log=True):
        auth_log = f'harbor_auth = {self.get_harbor_auth_display()}'
        ban_seconds = cache.ttl(f'{constants.CACHE_KEY_HARBOR_BAN_PREFIX}{self.id}')

        def log(s):
            if should_log:
                logger.info(s)

        if ban_seconds > 0:
            log(f'dj auth requested by {self}: denied ({auth_log}, but BANNED with {ban_seconds} seconds left)')
            return False

        elif self.harbor_auth == self.HarborAuth.ALWAYS:
            log(f'dj auth requested by {self}: allowed ({auth_log})')
            return True

        elif self.harbor_auth == self.HarborAuth.GOOGLE_CALENDAR:
            if config.GOOGLE_CALENDAR_ENABLED:
                if self.show_times:
                    if now is None:
                        now = timezone.now()
                    entry_grace = datetime.timedelta(minutes=self.gcal_entry_grace_minutes)
                    exit_grace = datetime.timedelta(minutes=self.gcal_exit_grace_minutes)
                    for show_time in self.show_times:
                        lower, upper = show_time
                        if (lower - entry_grace) <= now <= (upper + exit_grace):
                            log(f'dj auth requested by {self}: allowed ({auth_log} and {now} in time bounds - '
                                f'{timezone.localtime(lower)} [{entry_grace} entry grace] - '
                                f'{timezone.localtime(upper)} [{exit_grace} exit grace])')
                            return upper + exit_grace
                    else:
                        log(f'dj auth requested by {self}: denied ({auth_log} with {now} not in time bounds for '
                            f'{len(self.show_times)} show times)')
                        return False
                else:
                    log(f'dj auth requested by {self}: denied ({auth_log} with no show times)')
                    return False
            else:
                log(f'dj auth requested by {self}: allowed ({auth_log}, however GOOGLE_CALENDAR_ENABLED = False, '
                    f'so treating this like harbor_auth = {self.HarborAuth.ALWAYS.label})')
                return True
        else:
            log(f'dj auth requested by {self}: denied ({auth_log})')
            return False


def audio_asset_file_upload_to(instance, filename):
    return f'{instance.UPLOAD_DIR}/{filename}'


Metadata = namedtuple('Metadata', ('format', 'duration', 'artist', 'album', 'title'))


class AudioAssetBase(DirtyFieldsMixin, TimestampedModel):
    class Status(models.TextChoices):
        PENDING = '-', 'processing queued'
        PROCESSING = 'p', 'processing'
        FAILED = 'f', 'processing failed'
        READY = 'r', 'ready for play'

    UNNAMED_TRACK = 'Untitled Track'
    UPLOAD_DIR = 'assets'
    TITLE_FIELDS = TITLE_FIELDS_PRINT_SORTED = ('title',)
    FFMPEG_ACCEPTABLE_FORMATS = ('mp3', 'ogg', 'flac')

    title = TruncatingCharField('title', max_length=255, blank=True, db_index=True,
                                help_text="If left empty, a title will be generated from the file's metadata.")
    uploader = models.ForeignKey(User, verbose_name='uploader', on_delete=models.SET_NULL, null=True)
    file_basename = models.CharField(max_length=512)
    file = models.FileField('audio file', max_length=512, blank=True, upload_to=audio_asset_file_upload_to,
                            help_text='You can provide either an uploaded audio file or a URL to an external asset.')
    duration = models.DurationField('Audio duration', default=datetime.timedelta(0))
    fingerprint = models.UUIDField(null=True, db_index=True)  # 32 byte md5 = a UUID
    status = models.CharField('status', max_length=1, choices=Status.choices, default=Status.PENDING, db_index=True,
                              help_text='You will be able to edit this asset when status is "ready for play."')
    task_id = models.UUIDField(null=True)

    def __init__(self, *args, **kwargs):
        self.pre_convert_filename = kwargs.pop('pre_convert_filename', None)
        self.run_conversion_after_save = False
        self.run_download_after_save_url = None  # Set by model form
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
    def local_filename(self):
        if self.file:
            if isinstance(self.file.file, TemporaryUploadedFile):
                return self.file.file.temporary_file_path()
            else:
                return self.file.path

    @staticmethod
    def run_metadata(filename):
        # We want at least one audio channel
        cmd = subprocess.run(['ffprobe', '-i', filename, '-print_format', 'json', '-hide_banner', '-loglevel',
                              'error', '-show_format', '-show_error', '-show_streams', '-select_streams', 'a:0'],
                             text=True, capture_output=True)

        kwargs = {}
        if cmd.returncode == 0:
            ffprobe_data = json.loads(cmd.stdout)
            if ffprobe_data and ffprobe_data['streams'] and ffprobe_data['format']:
                kwargs.update({'format': ffprobe_data['format']['format_name'],
                               'duration': datetime.timedelta(seconds=math.ceil(float(
                                    ffprobe_data['streams'][0].get('duration') or 0)))})
            else:
                logger.warning(f'ffprobe returned a bad or empty response: {cmd.stdout}')
                return None
        else:
            logger.warning(f'ffprobe returned {cmd.returncode}: {cmd.stderr}')
            return None

        cmd = subprocess.run(['exiftool', '-json', filename], text=True, capture_output=True)
        if cmd.returncode == 0:
            exiftool_data = json.loads(cmd.stdout)[0]
            for field in ('artist', 'album', 'title'):
                kwargs[field] = exiftool_data.get(field.title(), '')
        else:
            logger.warning(f'exiftool returned {cmd.returncode}, using ffprobe for metadata')
            ffprobe_tags = ffprobe_data['format'].get('tags', {})
            for field in ('artist', 'album', 'title'):
                kwargs[field] = ffprobe_tags.get(field, '')

        return Metadata(**kwargs)

    @cached_property
    def metadata(self):
        return self.run_metadata(self.local_filename)

    def clear_metadata_cache(self):
        try:
            del self.metadata
        except AttributeError:
            pass

    @cached_property
    def computed_fingerprint(self):
        cmd = subprocess.run(['ffmpeg', '-v', 'error',  '-i', self.local_filename, '-map', '0:a:0', '-f', 'md5', '-'],
                             text=True, capture_output=True)
        if cmd.returncode == 0 and cmd.stdout.startswith('MD5='):
            return uuid.UUID(cmd.stdout.removeprefix('MD5=').strip())
        else:
            logger.warning(f'ffmpeg (md5) return {cmd.returncode}: {cmd.stderr}')
            return None

    def clean(self, allow_conversion=True):
        if self.file:
            if not self.metadata:
                raise ValidationError("Failed to extract audio info from the file you've uploaded. Try another?")

            if 'file' in self.get_dirty_fields():
                if not self.fingerprint:
                    self.fingerprint = self.computed_fingerprint  # Pre-conversion to acceptable format

                if config.ASSET_DEDUPING and self.computed_fingerprint:
                    match = self._meta.model.objects.exclude(id=self.id, fingerprint=None).filter(
                        status=self.Status.READY, fingerprint=self.computed_fingerprint).first()
                    if match:
                        raise ValidationError(f'A duplicate audio file already exists with audio fingerprint: {match}.')

                if not self.file_basename:
                    # We want the _original_ filename for operations like conversion + default title
                    self.file_basename = os.path.basename(self.file.path)

                self.duration = self.metadata.duration

                if self.metadata.format in self.FFMPEG_ACCEPTABLE_FORMATS:
                    self.status = self.Status.READY

                    # Normalize extension if it's an acceptable format
                    file_name, file_ext = os.path.splitext(self.file.name)
                    correct_ext = self.metadata.format
                    if correct_ext != file_ext.lower()[1:]:
                        file_exists = os.path.exists(self.file.path)
                        if file_exists or isinstance(self.file.file, TemporaryUploadedFile):
                            # If it's pending and a UI based (TemporaryUploadedFile) upload, that's all we have to do
                            if file_exists:
                                # Otherwise the file already exists, so rename it
                                os.rename(self.file.path, f'{os.path.splitext(self.file.path)[0]}.{correct_ext}')
                            logger.info(f'normalized upload filename {self.file.name} => {file_name}.{correct_ext}')
                            self.file.name = f'{file_name}.{correct_ext}'
                elif allow_conversion:
                    self.run_conversion_after_save = True
                else:
                    raise ValidationError('asset in an invalid format and conversion not allowed')

            for field in self.TITLE_FIELDS:
                if not getattr(self, field):
                    # Special case, if we're editing the title and there's no artist field
                    if field == 'title' and 'album' not in self.TITLE_FIELDS:
                        self.title = ' - '.join(filter(None, (self.metadata.artist, self.metadata.title)))
                    else:
                        setattr(self, field, getattr(self.metadata, field))

            if not self.title:
                logger.warning('exiftool/ffprobe returned an empty title. Setting title from original file name.')
                self.title = os.path.splitext(self.file_basename)[0].replace('_', ' ').strip() or self.UNNAMED_TRACK

        else:
            self.file = self.fingerprint = None
            self.duration = datetime.timedelta(0)

    @cached_property
    def task_log_line(self):
        # This is property cached for the lifetime of the object so it isn't read twice with
        # different values by admin
        if self.status == self.Status.PROCESSING and self.task_id:
            return cache.get(f'{constants.CACHE_KEY_ASSET_TASK_LOG_PREFIX}{self.task_id}')

    def set_task_log_line(self, log_line):
        if self.task_id:
            cache.set(f'{constants.CACHE_KEY_ASSET_TASK_LOG_PREFIX}{self.task_id}', log_line)

    @after_db_commit
    def queue_conversion(self):
        from .tasks import asset_convert_to_acceptable_format
        task = asset_convert_to_acceptable_format(self)
        self.task_id = task.id
        self._meta.model.objects.filter(id=self.id).update(task_id=task.id)

    @after_db_commit
    def queue_download(self, url, set_title=''):
        from .tasks import asset_download_external_url
        task = asset_download_external_url(self, url, title=set_title)
        self.task_id = task.id
        self._meta.model.objects.filter(id=self.id).update(task_id=task.id)

    def save(self, *args, **kwargs):
        run_conversion = False
        run_download_url = set_title = None

        if self.status == self.Status.PENDING and (self.run_conversion_after_save or self.run_download_after_save_url):
            self.status == self.Status.PROCESSING
            if self.run_conversion_after_save:
                run_conversion = True
            else:
                run_download_url = self.run_download_after_save_url
                set_title = self.title
                self.title = f'Downloading {self.run_download_after_save_url}'
        super().save(*args, **kwargs)

        if run_conversion:
            self.queue_conversion()
        elif run_download_url:
            self.queue_download(url=run_download_url, set_title=set_title)

    def full_title(self, include_duration=True):
        s = (' - '.join(filter(None, (getattr(self, field, None) for field in self.TITLE_FIELDS_PRINT_SORTED)))
             or self.UNNAMED_TRACK)
        if include_duration and self.duration != datetime.timedelta(0):
            if self.duration >= datetime.timedelta(hours=1):
                s += f' [{self.duration}]'
            else:
                seconds = int(self.duration.total_seconds())
                s += f' [{seconds // 60}:{seconds % 60:02d}]'
        return s

    def __str__(self):
        return self.full_title()
