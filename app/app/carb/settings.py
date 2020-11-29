from collections import OrderedDict
import os

from django.utils.safestring import mark_safe

import environ


env = environ.Env()
if os.path.exists('/.env'):
    env.read_env('/.env')

BASE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SECRET_KEY = env('SECRET_KEY', default='topsecret')

DEBUG = env.bool('DEBUG', default=False)
ICECAST_ENABLED = env.bool('ICECAST_ENABLED', default=False)
ZOOM_ENABLED = env.bool('ZOOM_ENABLED', default=False)
EMAIL_ENABLED = env.bool('EMAIL_ENABLED', default=False)
HARBOR_TELNET_ENABLED = env.bool('HARBOR_TELNET_ENABLED', default=False)
DOMAIN_NAME = env('DOMAIN_NAME', default='localhost')
TIME_ZONE = env('TIMEZONE', default='US/Pacific')

ALLOWED_HOSTS = ['app', 'localhost', DOMAIN_NAME]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    # Django
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'carb.apps.CARBAdminConfig',

    # Third-party
    'constance',
    'django_extensions',
    'huey.contrib.djhuey',

    # Local
    'api',
    'autodj',
    'broadcast',
    'common',  # users/permissions, Base classes (audio assets, etc), extra Constance code
    'gcal',
    'services',
    'webui',

    # Cleanup files after model deletion, needs to go last
    'django_cleanup',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'common.middleware.UserTimezoneMiddleware',
]

ROOT_URLCONF = 'carb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # To override admin templates
        'DIRS': [f'{BASE_DIR}/carb/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'constance.context_processors.config',
                'carb.context_processors.carb_extra_context',
            ],
        },
    },
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '[%(asctime)s] %(levelname)s:%(name)s:%(lineno)s:%(funcName)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        },
    },
    'loggers': {
        'carb': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },

}

WSGI_APPLICATION = 'carb.wsgi.application'

# In order to read uploaded audio metadata, we need a temporary file to exist
FILE_UPLOAD_HANDLERS = ('django.core.files.uploadhandler.TemporaryFileUploadHandler',)

LOGIN_URL = '/login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

if EMAIL_ENABLED:
    EMAIL_HOST = 'email'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'db',
        'PORT': 5432,
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis',
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                    'CONNECTION_POOL_KWARGS': {'max_connections': 10}},
        'KEY_PREFIX': 'cache'
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

LANGUAGE_CODE = 'en-us'

USE_I18N = False
USE_L10N = False
USE_TZ = True
# If we ever translate this app (USE_L10N/USE_I18N), we'll need to figure out a way to show seconds
SHORT_DATETIME_FORMAT = 'm/d/Y g:i:s a'
DATETIME_FORMAT = 'N j, Y, g:i:s a'

AUTH_USER_MODEL = 'common.User'

STATIC_URL = '/static/'
STATIC_ROOT = '/static_root'
MEDIA_URL = '/media/'
MEDIA_ROOT = '/media_root'

HUEY = {
    'name': 'carb',
    'immediate': False,
    'connection': {'host': 'redis'},
    # 'connection_pool': ConnectionPool(host='redis', max_connections=5),
}

# XXX debug
SHELL_PLUS_IMPORTS = [
    'from constance import config',
    'from django_redis import get_redis_connection',
    'from carb import constants',
    'from gcal.tasks import sync_google_calendar_api',
    'from webui.tasks import preload_sample_audio_assets, preload_sample_stopsets, stop_zoom_broadcast',
    'from broadcast.tasks import play_broadcast',
    'from common.tasks import asset_download_external_url',
    'from services.tasks import purge_playout_log_entries',
]

CONSTANCE_BACKEND = 'constance.backends.redisd.RedisBackend'
CONSTANCE_REDIS_CONNECTION_CLASS = 'django_redis.get_redis_connection'
CONSTANCE_SUPERUSER_ONLY = False

CONSTANCE_ADDITIONAL_FIELDS = {
    'external_asset_encoding_choices': ['django.forms.fields.ChoiceField', {
        'widget': 'django.forms.Select',
        'choices': (('mp3', 'MP3'), ('vorbis', 'Ogg Vorbis'), ('flac', 'FLAC'))
    }],
    'external_asset_bitrate_choices': ['django.forms.fields.ChoiceField', {
        'widget': 'django.forms.Select',
        'choices': (('64K', '64kbit'), ('128K', '128kbit'), ('192K', '192kbit'), ('256K', '256kbit'),
                    ('320K', '320kbit')),
    }],
    'file': ['django.forms.FileField', {'widget': 'common.widgets.AlwaysClearableFileInput', 'required': False}],
    'email': ['django.forms.EmailField', {}],
    'char': ['django.forms.CharField', {'required': False}],
    'positive_int': ['django.forms.IntegerField', {'min_value': 0}],
    'positive_float': ['django.forms.FloatField', {'min_value': 0.0}],
}

CONSTANCE_CONFIG = OrderedDict((
    ('STATION_NAME', ('Crazy Arms Radio Station', 'The name of your radio station.', 'char')),
    ('PLAYOUT_LOG_PURGE_DAYS', (14, "The number of days to keep playout log entries after which they're purged. "
                                'Set to 0 to keep playout log entries forever.', 'positive_int')),
    ('HARBOR_COMPRESSION_NORMALIZATION', (True, 'Enable compression and normalization on harbor stream.')),
    ('HARBOR_TRANSITION_SECONDS', (2.5, 'Fadeout time in seconds when transitioning between harbor sources. '
                                   'Set to 0 for no fadeout.', 'positive_float')),
    ('HARBOR_TRANSITION_WITH_SWOOSH', (False, 'Transition between harbor sources with a ~1 second swoosh effect.')),
    ('HARBOR_SWOOSH_AUDIO_FILE', (False, 'Audio file for the swoosh (if enabled). Sound be short, ie under 3-4 '
                                  'seconds.', 'file')),
    ('HARBOR_MAX_SECONDS_SILENCE_BEFORE_TRANSITION', (15, 'The maximum number of seconds of silence on a live source '
                                                      '(eg. Zoom or live DJs) until it will be considered inactive.',
                                                      'positive_int')),
    ('HARBOR_FAILSAFE_AUDIO_FILE', (False, "Failsafe audio file that the harbor should play if there's nothing else to "
                                    'stream.', 'file')),
    ('UPSTREAM_FAILSAFE_AUDIO_FILE', (False, 'Failsafe audio file that should be broadcast to upstream servers if we '
                                      "can't connect to the harbor, ie the harbor failed to start.", 'file')),
    ('AUTODJ_ENABLED', (True, 'Whether or not to run an AutoDJ on the harbor.')),
    ('AUTODJ_STOPSETS_ENABLED', (False, 'Whether or not the AutoDJ plays stop sets (for ADs, PSAs, Station IDs, etc)')),
    ('AUTODJ_STOPSETS_ONCE_PER_MINUTES', (20, 'How often a stop set should be played (in minutes)', 'positive_int')),
    ('AUTODJ_PLAYLISTS_ENABLED', (True, 'Whether or not the AutoDJ should use playlists')),
    ('AUTODJ_ANTI_REPEAT_ENABLED', (True, 'Whether or not the AutoDJ should attempt its anti-repeat algorithm. Note if '
                                          "you have too few tracks, this won't work.")),  # unneeded if artists+tracks=0
    ('AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT',
        (50, 'Number of tracks to avoid to avoid repeating (if possible). Set to 0 to disable.', 'positive_int')),
    ('AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST',
        (15, 'Number of tracks to avoid playing the same artist (if possible). Set to 0 to disable.',
         'positive_int')),
    ('EXTERNAL_ASSET_ENCODING', ('mp3', 'Encoding of downloaded external assets.', 'external_asset_encoding_choices')),
    ('EXTERNAL_ASSET_BITRATE', ('128K', 'Bitrate (quality) of downloaded external assets. Unused for FLAC.',
                                'external_asset_bitrate_choices')),
    ('GOOGLE_CALENDAR_ENABLED', (False, 'Enabled Google Calendar based authentication for DJs.')),
    ('GOOGLE_CALENDAR_ID', ('example@gmail.com', 'Google Calendar ID.', 'char')),
    ('GOOGLE_CALENDAR_CREDENTIALS_JSON', (
        '', mark_safe('Past the contents of your Google Service JSON Account Key here (a <code>credentials.json</code> '
                      'file).<br>For more info from Google about this please <a href="https://cloud.google.com/docs'
                      '/authentication/getting-started" target="_blank">click here</a>.'))),
))

if ICECAST_ENABLED:
    CONSTANCE_CONFIG.update(OrderedDict((
        ('ICECAST_LOCATION', ('The World', 'Location setting for the Icecast server.', 'char')),
        ('ICECAST_ADMIN_EMAIL', (f'admin@{DOMAIN_NAME}', 'The admin email setting for the Icecast server.', 'email')),
        ('ICECAST_ADMIN_PASSWORD', ('', 'Admin password for the Icecast server.', 'char')),
        ('ICECAST_SOURCE_PASSWORD', ('', 'Source password for the Icecast server.', 'char')),
        ('ICECAST_RELAY_PASSWORD', ('', 'Relay password for the Icecast server.', 'char')),
        ('ICECAST_MAX_CLIENTS', (0, 'Max connected clients allowed the Iceacst server (0 for unlimited).',
                                 'positive_int')),
        ('ICECAST_MAX_SOURCES', (0, 'Max sources allowed to connect to the Icecast server (0 for unlimited).',
                                 'positive_int')),
    )))

CONSTANCE_CONFIG_FIELDSETS = OrderedDict((
    ('General Options', ('STATION_NAME', 'PLAYOUT_LOG_PURGE_DAYS')),
    ('Harbor Configuration', ('HARBOR_COMPRESSION_NORMALIZATION', 'HARBOR_TRANSITION_WITH_SWOOSH',
                              'HARBOR_SWOOSH_AUDIO_FILE', 'HARBOR_TRANSITION_SECONDS',
                              'HARBOR_MAX_SECONDS_SILENCE_BEFORE_TRANSITION', 'HARBOR_FAILSAFE_AUDIO_FILE',
                              'UPSTREAM_FAILSAFE_AUDIO_FILE')),
    ('AutoDJ Configuration', ('AUTODJ_ENABLED', 'AUTODJ_ANTI_REPEAT_ENABLED', 'AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT',
                              'AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST', 'AUTODJ_PLAYLISTS_ENABLED',
                              'AUTODJ_STOPSETS_ENABLED', 'AUTODJ_STOPSETS_ONCE_PER_MINUTES')),
    ('Externally Downloaded Audio Assets', ('EXTERNAL_ASSET_ENCODING', 'EXTERNAL_ASSET_BITRATE')),
    ('Google Calendar Based Authentication', ('GOOGLE_CALENDAR_ENABLED', 'GOOGLE_CALENDAR_ID',
                                              'GOOGLE_CALENDAR_CREDENTIALS_JSON')),
))

if ICECAST_ENABLED:
    CONSTANCE_CONFIG_FIELDSETS.update(OrderedDict((
        ('Icecast Settings', ('ICECAST_LOCATION', 'ICECAST_ADMIN_EMAIL', 'ICECAST_ADMIN_PASSWORD',
                              'ICECAST_SOURCE_PASSWORD', 'ICECAST_RELAY_PASSWORD', 'ICECAST_MAX_CLIENTS',
                              'ICECAST_MAX_SOURCES')),
    )))
