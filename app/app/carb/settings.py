from collections import OrderedDict
import os

import environ
from redis import ConnectionPool


env = environ.Env()
env.read_env('/.env')

BASE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SECRET_KEY = env('SECRET_KEY')

DEBUG = env.bool('DEBUG', default=False)
ICECAST_ENABLED = env.bool('ICECAST_ENABLED', default=False)
ZOOM_ENABLED = env.bool('ZOOM_ENABLED', default=False)
EMAIL_ENABLED = env.bool('EMAIL_ENABLED', default=False)
DOMAIN_NAME = env('DOMAIN_NAME')

ALLOWED_HOSTS = ['app']
if DEBUG:
    ALLOWED_HOSTS.append('localhost')

INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'django_extensions',
    'constance',
    'huey.contrib.djhuey',

    # Local
    'api',
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
]

ROOT_URLCONF = 'carb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'constance.context_processors.config',
                'common.context_processors.settings',
            ],
        },
    },
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '[%(asctime)s] %(levelname)s:%(name)s:%(filename)s:%(lineno)s:%(funcName)s: %(message)s',
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
    },
}

WSGI_APPLICATION = 'carb.wsgi.application'

# In order to read uploaded audio metadata, we need a temporary file to exist
FILE_UPLOAD_HANDLERS = ('django.core.files.uploadhandler.TemporaryFileUploadHandler',)

LOGIN_URL = '/login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

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
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
        'KEY_PREFIX': 'cache'
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'US/Pacific'

USE_I18N = True

USE_L10N = True

USE_TZ = True

AUTH_USER_MODEL = 'common.User'

STATIC_URL = '/static/'
STATIC_ROOT = '/static_root'
MEDIA_URL = '/media/'
MEDIA_ROOT = '/media_root'

HUEY = {
    'name': 'carb',
    'immediate': False,
    'connection_pool': ConnectionPool(host='redis', max_connections=10),
}

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

CONSTANCE_CONFIG = {
    'MY_SELECT_KEY': ('yes', 'select yes or no', 'yes_no_null_select'),
}

CONSTANCE_CONFIG = OrderedDict((
    ('STATION_NAME', ('Crazy Arms Radio Station', 'The name of your radio station')),
    ('EXTERNAL_ASSET_ENCODING', ('mp3', 'Encoding of downloaded external assets', 'EXTERNAL_ASSET_ENCODING')),
    ('EXTERNAL_ASSET_BITRATE', ('128K', 'Bitrate (quality) of downloaded external assets. Unused for FLAC.',
                                'EXTERNAL_ASSET_BITRATE')),
    ('GOOGLE_CALENDAR_ENABLED', (False, 'Enabled Google Calendar based authentication for DJs')),
    ('GOOGLE_CALENDAR_ID', ('example@gmail.com', 'Google Calendar ID')),
    ('GOOGLE_CALENDAR_CREDENTIALS_JSON', ('', 'credentials.json service file from Google (TODO: document better)')),
))

if ICECAST_ENABLED:
    CONSTANCE_CONFIG.update(OrderedDict((
        ('ICECAST_LOCATION', ('The World', 'Location setting for the Icecast server')),
        ('ICECAST_ADMIN_EMAIL', (f'admin@{env("DOMAIN_NAME")}', 'The admin email setting for the Icecast server')),
        ('ICECAST_ADMIN_PASSWORD', ('hackme', 'Admin password for the Icecast server')),
        ('ICECAST_SOURCE_PASSWORD', ('hackme', 'Source password for the Icecast server')),
        ('ICECAST_RELAY_PASSWORD', ('hackme', 'Relay password for the Icecast server')),
        ('ICECAST_MAX_CLIENTS', (0, 'Max connected clients allowed the Iceacst server (0 for unlimited)')),
        ('ICECAST_MAX_SOURCES', (0, 'Max sources allowed to connect to the Icecast server (0 for unlimited)')),
    )))

CONSTANCE_CONFIG_FIELDSETS = OrderedDict((
    ('General Options', ('STATION_NAME',)),
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
