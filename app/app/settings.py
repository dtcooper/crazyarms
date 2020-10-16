from collections import OrderedDict
import os

import environ

env = environ.Env()
env.read_env('/.env')

BASE_DIR = os.path.dirname(__file__)
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
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'constance',
    'carb',
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

ROOT_URLCONF = 'urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'constance.context_processors.config',
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'carb.context_processors.settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'wsgi.application'


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

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'US/Pacific'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = '/static_root'
CELERY_BROKER_URL = 'redis://redis'


CONSTANCE_BACKEND = 'constance.backends.redisd.RedisBackend'
CONSTANCE_REDIS_CONNECTION = {'host': 'redis'}

CONSTANCE_CONFIG = OrderedDict((
    ('STATION_NAME', ('Crazy Arms Radio Station', 'The name of your radio station')),
    ('GCAL_AUTH_ENABLED', (False, 'Enabled Google Calendar based authentication for DJs')),
    ('GCAL_AUTH_CREDENTIALS_JSON', ('', 'credentials.json service file from Google (TODO: document better)')),
))

if ICECAST_ENABLED:
    CONSTANCE_CONFIG.update(OrderedDict((
        ('ICECAST_LOCATION', ('The World', 'Location setting for the Icecast server')),
        ('ICECAST_ADMIN_EMAIL', (f'admin@{env("DOMAIN_NAME")}', 'The admin email address setting for the Icecast server')),
        ('ICECAST_ADMIN_PASSWORD', ('hackme', 'Admin password for the Icecast server')),
        ('ICECAST_SOURCE_PASSWORD', ('hackme', 'Source password for the Icecast server')),
        ('ICECAST_RELAY_PASSWORD', ('hackme', 'Relay password for the Icecast server')),
        ('ICECAST_MAX_CLIENTS', (0, 'Max connected clients allowed the Iceacst server (0 for unlimited)')),
        ('ICECAST_MAX_SOURCES', (0, 'Max sources allowed to connect to the Icecast server (0 for unlimited)')),
    )))

CONSTANCE_CONFIG_FIELDSETS = OrderedDict((
    ('General Options', ('STATION_NAME',)),
    ('Google Calendar Based Authentication', ('GCAL_AUTH_ENABLED', 'GCAL_AUTH_CREDENTIALS_JSON')),
))

if ICECAST_ENABLED:
    CONSTANCE_CONFIG_FIELDSETS.update(OrderedDict((
        ('Icecast Settings', ('ICECAST_LOCATION', 'ICECAST_ADMIN_EMAIL', 'ICECAST_ADMIN_PASSWORD',
                              'ICECAST_SOURCE_PASSWORD', 'ICECAST_RELAY_PASSWORD', 'ICECAST_MAX_CLIENTS',
                              'ICECAST_MAX_SOURCES')),
    )))
