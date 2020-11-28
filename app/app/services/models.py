from django.db import models
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe

from autodj.models import AudioAsset
from common.models import User, TruncatingCharField


class UpstreamServer(models.Model):
    class Encoding(models.TextChoices):
        MP3 = 'mp3', 'MP3'
        AAC = 'fdkaac', 'AAC'
        OGG = 'vorbis.cbr', 'OGG Vorbis'
        FFMPEG = 'ffmpeg', 'ffmpeg (custom additional arguments needed)'

    class Protocol(models.TextChoices):
        HTTP = 'http', 'http'
        HTTPS = 'https', 'https (secure)'

    name = models.SlugField('name', max_length=20, unique=True,
                            help_text='Unique codename to identify this upstream server.')
    hostname = models.CharField('hostname', max_length=255,
                                help_text='Hostname for the server, eg. example.com')
    protocol = models.CharField('protocol', max_length=5, choices=Protocol.choices, default=Protocol.HTTP,
                                help_text="The protocol for the server, if unsure it's likely http")
    port = models.PositiveSmallIntegerField('port', help_text='Port for this server, eg. 8000')
    telnet_port = models.PositiveIntegerField()
    username = models.CharField('username', max_length=255, default='source')
    password = models.CharField('password', max_length=255)
    mount = models.CharField('mount point', max_length=255,
                             help_text='Mount point for the upstream server, eg. /stream')
    encoding = models.CharField('encoding format', max_length=20, choices=Encoding.choices, default=Encoding.MP3)
    bitrate = models.PositiveSmallIntegerField(
        'bitrate', null=True, blank=True, help_text="Encoding bitrate (kbits), blank for a sane default or ffmpeg.")
    mime = models.CharField('MIME format', max_length=50, help_text='MIME format, ie audio/mpeg, leave blank for '
                            'Liquidsoap to guess. (Needed for ffmpeg.)', blank=True)
    encoding_args = models.JSONField(
        'additional arguments for encoding', blank=True, null=True, default=None, help_text=mark_safe(
            # TODO dynamic Liquidsoap version somehow
            'Enter any additional arguments for the encoder here. Advanced use cases only, see the '
            '<a href="https://www.liquidsoap.info/doc-1.4.3/encoding_formats.html" target="_blank">Liquidsoap docs '
            'here</a> for more info. Leave empty or <code>null</code> for none.'))

    class Meta:
        ordering = ('id',)
        unique_together = ('hostname', 'port', 'mount')

    def __str__(self):
        s = f'{self.protocol}://{self.username}@{self.hostname}:{self.port}/{self.mount} ({self.get_encoding_display()}'
        if self.bitrate:
            s += f' @ {self.bitrate} kbit/s'
        return f'{s})'

    def save(self, *args, **kwargs):
        self.mount = self.mount.removeprefix('/')

        if not self.telnet_port:
            # Find a free port
            port, used_ports = 1234, set(UpstreamServer.objects.values_list('telnet_port', flat=True))
            while port in used_ports:
                port += 1
            self.telnet_port = port

        return super().save(*args, **kwargs)

    # @cached_property
    # def telnet_port(self):
    #     return 1234 + type(self).objects.filter(id__lt=self.id).count()


class PlayoutLogEntry(models.Model):
    class EventType(models.TextChoices):
        # These are used by templates/services/*.liq files, so be mindful before changing
        TRACK = 'track', 'Track'
        LIVE_DJ = 'dj', 'Live DJ'
        GENERAL = 'general', 'General'
        SOURCE_TRANSITION = 'source', 'Source Transition'

    created = models.DateTimeField('Date', auto_now_add=True, db_index=True)
    event_type = models.CharField('Type', max_length=10, choices=EventType.choices, default=EventType.GENERAL)
    description = TruncatingCharField('Entry', max_length=500)
    active_source = TruncatingCharField('Active Source', max_length=50, default='N/A')
    audio_asset = models.ForeignKey(AudioAsset, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ('-created',)
        verbose_name = 'playout log entry'
        verbose_name_plural = 'playout logs'
