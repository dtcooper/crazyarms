from common.models import AudioAssetBase, TruncatingCharField


class AudioAsset(AudioAssetBase):
    TITLE_FIELDS = ('title', 'artist', 'album')
    artist = TruncatingCharField('artist', max_length=255, blank=True,
                                 help_text="If left empty, an artist will be generated from the file's metadata.")
    album = TruncatingCharField('album', max_length=255, blank=True,
                                help_text="If left empty, an album will be generated from the file's metadata.")

    class Meta:
        verbose_name = 'audio asset'
        verbose_name_plural = 'audio assets'
