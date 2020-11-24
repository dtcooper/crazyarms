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

SHELL_PLUS_IMPORTS = [
    'from constance import config',
]

CONSTANCE_BACKEND = 'constance.backends.redisd.RedisBackend'
CONSTANCE_REDIS_CONNECTION_CLASS = 'django_redis.get_redis_connection'
CONSTANCE_SUPERUSER_ONLY = False

CONSTANCE_ADDITIONAL_FIELDS = {
    'EXTERNAL_ASSET_ENCODING': ['django.forms.fields.ChoiceField', {
        'widget': 'django.forms.Select',
        'choices': (('mp3', 'MP3'), ('vorbis', 'Ogg Vorbis'), ('flac', 'FLAC'))
    }],
    'EXTERNAL_ASSET_BITRATE': ['django.forms.fields.ChoiceField', {
        'widget': 'django.forms.Select',
        'choices': (('64K', '64kbit'), ('128K', '128kbit'), ('192K', '192kbit'), ('256K', '256kbit'),
                    ('320K', '320kbit')),
    }],
}

CONSTANCE_CONFIG = OrderedDict((
    ('STATION_NAME', ('Crazy Arms Radio Station', 'The name of your radio station.')),
    ('PLAYOUT_LOG_PURGE_DAYS', (14, "The number of days to keep playout log entries after which they're purged. "
                                'Set to 0 to keep playout log entries forever.')),
    ('HARBOR_COMPRESSION_NORMALIZATION', (True, 'Enable compression and normalization on harbor stream.')),
    ('HARBOR_TRANSITION_SECONDS', (2.5, 'Fadeout time in seconds when transitioning between harbor sources. '
                                        'Set to 0 for no fadeout.')),
    ('HARBOR_TRANSITION_WITH_SWOOSH', (False, 'Transition between harbor sources with a ~1 second swoosh effect.')),
    ('HARBOR_MAX_SECONDS_SILENCE_BEFORE_TRANSITION', (15, 'The maximum number of seconds of silence on a live source '
                                                      '(eg. Zoom or live DJs) until it will be considered inactive.')),
    ('AUTODJ_ENABLED', (True, 'Whether or not to run an AutoDJ on the harbor.')),
    ('AUTODJ_ANTI_REPEAT', (True, 'Whether or not the AutoDJ should attempt its anti-repeat algorithm. Note if you '
                            "have too few tracks, this won't work.")),
    ('AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT',
        (50, 'Number of tracks to avoid to avoid repeating (if possible). Set to 0 to disable.')),
    ('AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST',
        (15, 'Number of tracks to avoid playing the same artist (if possible). Set to 0 to disable.')),
    ('EXTERNAL_ASSET_ENCODING', ('mp3', 'Encoding of downloaded external assets.', 'EXTERNAL_ASSET_ENCODING')),
    ('EXTERNAL_ASSET_BITRATE', ('128K', 'Bitrate (quality) of downloaded external assets. Unused for FLAC.',
                                'EXTERNAL_ASSET_BITRATE')),
    ('GOOGLE_CALENDAR_ENABLED', (False, 'Enabled Google Calendar based authentication for DJs.')),
    ('GOOGLE_CALENDAR_ID', ('example@gmail.com', 'Google Calendar ID.')),
    ('GOOGLE_CALENDAR_CREDENTIALS_JSON', (
        '', mark_safe('Past the contents of your Google Service JSON Account Key here (a <code>credentials.json</code> '
                      'file).<br>For more info from Google about this please <a href="https://cloud.google.com/docs'
                      '/authentication/getting-started" target="_blank">click here</a>.'))),
))

if ICECAST_ENABLED:
    CONSTANCE_CONFIG.update(OrderedDict((
        ('ICECAST_LOCATION', ('The World', 'Location setting for the Icecast server.')),
        ('ICECAST_ADMIN_EMAIL', (f'admin@{DOMAIN_NAME}', 'The admin email setting for the Icecast server.')),
        ('ICECAST_ADMIN_PASSWORD', ('', 'Admin password for the Icecast server.')),
        ('ICECAST_SOURCE_PASSWORD', ('', 'Source password for the Icecast server.')),
        ('ICECAST_RELAY_PASSWORD', ('', 'Relay password for the Icecast server.')),
        ('ICECAST_MAX_CLIENTS', (0, 'Max connected clients allowed the Iceacst server (0 for unlimited).')),
        ('ICECAST_MAX_SOURCES', (0, 'Max sources allowed to connect to the Icecast server (0 for unlimited).')),
    )))

CONSTANCE_CONFIG_FIELDSETS = OrderedDict((
    ('General Options', ('STATION_NAME', 'PLAYOUT_LOG_PURGE_DAYS')),
    ('Harbor Configuration', ('HARBOR_COMPRESSION_NORMALIZATION', 'HARBOR_TRANSITION_WITH_SWOOSH',
                              'HARBOR_TRANSITION_SECONDS', 'HARBOR_MAX_SECONDS_SILENCE_BEFORE_TRANSITION')),
    ('AutoDJ Configuration', ('AUTODJ_ENABLED', 'AUTODJ_ANTI_REPEAT', 'AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT',
                              'AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST')),
    ('Externally Downloaded Assets', ('EXTERNAL_ASSET_ENCODING', 'EXTERNAL_ASSET_BITRATE')),
    ('Google Calendar Based Authentication', ('GOOGLE_CALENDAR_ENABLED', 'GOOGLE_CALENDAR_ID',
                                              'GOOGLE_CALENDAR_CREDENTIALS_JSON')),
))

if ICECAST_ENABLED:
    CONSTANCE_CONFIG_FIELDSETS.update(OrderedDict((
        ('Icecast Settings', ('ICECAST_LOCATION', 'ICECAST_ADMIN_EMAIL', 'ICECAST_ADMIN_PASSWORD',
                              'ICECAST_SOURCE_PASSWORD', 'ICECAST_RELAY_PASSWORD', 'ICECAST_MAX_CLIENTS',
                              'ICECAST_MAX_SOURCES')),
    )))
