from django.db import models
from django.utils.safestring import mark_safe


class UpstreamServer(models.Model):
    class Encoding(models.TextChoices):
        MP3 = 'm', 'MP3'
        AAC = 'a', 'AAC'
        OGG = 'o', 'OGG Vorbis'
        FFMPEG = 'f', 'ffmpeg (custom)'

    class Protocol(models.TextChoices):
        HTTP = 'http', 'http'
        HTTPS = 'https', 'https (secure)'

    def __str__(self):
        s = f'{self.protocol}://{self.username}@{self.hostname}:{self.port}/{self.mount} ({self.get_encoding_display()}'
        if self.bitrate:
            s += f' @ {self.bitrate} kbit/s'
        return f'{s})'

    def save(self, *args, **kwargs):
        self.mount = self.mount.removeprefix('/')
        return super().save(*args, **kwargs)

    name = models.SlugField('name', max_length=20, unique=True,
                            help_text='Unique codename to identify this upstream server.')
    hostname = models.CharField('hostname', max_length=255,
                                help_text='Hostname for the server, eg. example.com')
    protocol = models.CharField('protocol', max_length=5, choices=Protocol.choices, default=Protocol.HTTP,
                                help_text="The protocol for the server, if unsure it's likely http")
    port = models.PositiveSmallIntegerField('port', help_text='Port for this server, eg. 8000')
    username = models.CharField('username', max_length=255, default='source')
    password = models.CharField('password', max_length=255)
    mount = models.CharField('mount point', max_length=255,
                             help_text='Mount point for the upstream server, eg. /stream')
    encoding = models.CharField('encoding format', max_length=1, choices=Encoding.choices, default=Encoding.MP3)
    bitrate = models.PositiveSmallIntegerField(
        'bitrate', null=True, blank=True, help_text="Encoding bitrate (kbits), leave blank for a sane default.")
    encoding_args = models.JSONField(
        'additional arguments for encoding', blank=True, null=True, default=None, help_text=mark_safe(
            # TODO dynamic Liquidsoap version somehow
            'Enter any additional arguments for the encoder here. Advanced use cases only, see the '
            '<a href="https://www.liquidsoap.info/doc-1.4.3/encoding_formats.html" target="_blank">Liquidsoap docs '
            'here</a> for more info. Leave empty or <code>null</code> for none.'))
