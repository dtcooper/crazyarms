import os

import environ

env = environ.Env(
    DEBUG=(bool, False)
)
env.read_env('/.env')

BASE_DIR = os.path.dirname(__file__)
SECRET_KEY = env('SECRET_KEY')

DEBUG = env('DEBUG')

ALLOWED_HOSTS = ['admin']
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

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = '/static_root'


CONSTANCE_BACKEND = 'constance.backends.redisd.RedisBackend'
CONSTANCE_REDIS_CONNECTION = {'host': 'redis'}

CONSTANCE_CONFIG = {
    'STATION_NAME': ('Crazy Arms Radio Station', 'The name of your radio station'),
    'ICECAST_ENABLED': (True, 'Whether or not to run a local Icecast server (kh fork)'),
    'ICECAST_LOCATION': ('The World', 'Location setting for local Icecast server'),
    'ICECAST_ADMIN_EMAIL': (f'admin@{env("DOMAIN_NAME")}', 'The admin email address setting for local Icecast server'),
    'ICECAST_MAX_BANDWITH': (0, 'Max bandwidth available for local Icecast server in MB, leave as 0 for unlimited'),
    'ICECAST_MAX_CLIENTS': (2500, 'Max connected clients allowed local Iceacst server.'),
    'ICECAST_MAX_SOURCES': (25, 'Max sources allowed to connect to local Icecast server.'),
}
