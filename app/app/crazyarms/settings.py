from collections import OrderedDict
import os

from django.utils.safestring import mark_safe

import environ

env = environ.Env()
if os.path.exists("/.env"):
    env.read_env("/.env")

BASE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
SECRET_KEY = env("SECRET_KEY")

DEBUG = env.bool("DEBUG", default=False)
DOMAIN_NAME = env("DOMAIN_NAME", default="localhost")
EMAIL_ENABLED = env.bool("EMAIL_ENABLED", default=False)
HARBOR_PORT = env.int("HARBOR_PORT", default=8001)
HARBOR_TEST_PORT = env.int("HARBOR_TEST_PORT", default=8002)
HARBOR_TELNET_WEB_ENABLED = env.bool("HARBOR_TELNET_WEB_ENABLED", default=False)
ICECAST_ENABLED = env.bool("ICECAST_ENABLED", default=False)
ICECAST_PORT = env.int("ICECAST_PORT", default=8000)
RTMP_ENABLED = env.bool("RTMP_ENABLED", default=False)
RTMP_PORT = env.int("RTMP_PORT", default=1935)
SFTP_PORT = env.int("SFTP_PORT", default=2022)
TIME_ZONE = env("TIMEZONE", default="US/Pacific")
ZOOM_ENABLED = env.bool("ZOOM_ENABLED", default=False)

ALLOWED_HOSTS = ["app", "localhost", "127.0.0.1", DOMAIN_NAME]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Custom admin site
    "crazyarms.apps.CrazyArmsAdminConfig",
    # Third-party
    "constance",
    "django_extensions",
    "django_select2",
    "django_unused_media",
    "huey.contrib.djhuey",
    # Local
    "api",
    "autodj",
    "broadcast",
    "common",  # users/permissions, Base classes (audio assets, etc), extra Constance code
    "gcal",
    "services",
    "webui",
]

if not os.environ.get("NO_DJANGO_CLEANUP"):  # May want to disable for testing
    INSTALLED_APPS.append("django_cleanup")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.UserTimezoneMiddleware",
]

ROOT_URLCONF = "crazyarms.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # To override admin templates
        "DIRS": [f"{BASE_DIR}/crazyarms/templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "constance.context_processors.config",
                "crazyarms.context_processors.crazyarms_extra_context",
            ],
        },
    },
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "[%(asctime)s] %(levelname)s:%(name)s:%(lineno)s:%(funcName)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "loggers": {
        "crazyarms": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}

WSGI_APPLICATION = "crazyarms.wsgi.application"

# In order to read uploaded audio metadata, we need a temporary file to exist
FILE_UPLOAD_HANDLERS = ("django.core.files.uploadhandler.TemporaryFileUploadHandler",)

LOGIN_URL = "/login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

if EMAIL_ENABLED:
    EMAIL_HOST = env("EMAIL_SMTP_SERVER")
    EMAIL_HOST_PASSWORD = env("EMAIL_SMTP_PASSWORD")
    EMAIL_HOST_USER = env("EMAIL_SMTP_USERNAME")
    EMAIL_PORT = env.int("EMAIL_SMTP_PORT")
    EMAIL_TIMEOUT = 10  # Longer than that and error occurs and we show a warning
    EMAIL_USE_TLS = env.bool("EMAIL_SMTP_TLS", default=(EMAIL_PORT == 587))


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "db",
        "PORT": 5432,
    }
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 10},
        },
        "KEY_PREFIX": "cache",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SELECT2_CACHE_BACKEND = "default"

LANGUAGE_CODE = "en-us"

USE_I18N = False
USE_L10N = False
USE_TZ = True
# If we ever translate this app (USE_L10N/USE_I18N), we'll need to figure out a way to show seconds
SHORT_DATETIME_FORMAT = "m/d/Y g:i:s a"
DATETIME_FORMAT = "N j, Y, g:i:s a"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "common.User"

STATIC_URL = "/static/"
STATIC_ROOT = "/static_root/"
MEDIA_URL = "/media/"
MEDIA_ROOT = "/media_root/"
AUDIO_IMPORTS_ROOT = "/imports_root/"
SFTP_UPLOADS_ROOT = "/sftp_root/"

HUEY = {
    "connection": {"host": "redis"},
    "expire_time": 60 * 60,
    "huey_class": "huey.PriorityRedisExpireHuey",
    "immediate": False,
    "name": "crazyarms",
    # 'connection_pool': ConnectionPool(host='redis', max_connections=5),
}

# XXX debug
SHELL_PLUS_IMPORTS = [
    "from constance import config",
    "from django_redis import get_redis_connection",
    "from crazyarms import constants",
    # tasks
    "from common.tasks import asset_convert_to_acceptable_format, asset_download_external_url, youtube_dl_daily_update,"
    " remove_unused_media_files_daily",
    "from gcal.tasks import sync_gcal_api",
    "from webui.tasks import stop_zoom_broadcast",
    "from api.tasks import process_sftp_upload",
    "from broadcast.tasks import play_broadcast",
    "from services.tasks import purge_playout_log_entries, liquidsoap_services_watchdog",
]

CONSTANCE_BACKEND = "constance.backends.redisd.RedisBackend"
CONSTANCE_REDIS_CONNECTION_CLASS = "django_redis.get_redis_connection"
CONSTANCE_SUPERUSER_ONLY = False

CONSTANCE_ADDITIONAL_FIELDS = {
    # in youtube-dl format, converted or ffmpeg in common/models.py:AudioAssetBase
    "asset_encoding_choices": [
        "django.forms.fields.ChoiceField",
        {
            "widget": "django.forms.Select",
            "choices": (("mp3", "MP3"), ("vorbis", "Ogg Vorbis"), ("flac", "FLAC")),
        },
    ],
    "asset_bitrate_choices": [
        "django.forms.fields.ChoiceField",
        {
            "widget": "django.forms.Select",
            "choices": (
                ("64K", "64kbit"),
                ("128K", "128kbit"),
                ("192K", "192kbit"),
                ("256K", "256kbit"),
                ("320K", "320kbit"),
            ),
        },
    ],
    "autodj_requests_choices": [
        "django.forms.fields.ChoiceField",
        {
            "widget": "django.forms.Select",
            # Careful: referred to by code text in autodj/models.py and webui/views.py
            "choices": (
                ("disabled", "Disabled (nobody)"),
                ("user", "Users"),
                ("perm", 'Users with "Program the AutoDJ" permissions'),
                ("superuser", "Administrators"),
            ),
        },
    ],
    "clearable_file": [
        "django.forms.FileField",
        {"widget": "common.widgets.AlwaysClearableFileInput", "required": False},
    ],
    "email": ["django.forms.EmailField", {}],
    "char": ["django.forms.CharField", {"required": False}],
    "required_char": ["django.forms.CharField", {"required": True}],
    "station_name": ["django.forms.CharField", {"required": True, "max_length": 40}],
    "positive_int": ["django.forms.IntegerField", {"min_value": 0}],
    "nonzero_positive_int": ["django.forms.IntegerField", {"min_value": 1}],
    "positive_float": ["django.forms.FloatField", {"min_value": 0.0}],
    "zoom_minutes": [
        "django.forms.IntegerField",
        # Per https://zoom.us/pricing, 30 hour show max
        {"min_value": 30, "max_value": 60 * 30},
    ],
}

CONSTANCE_CONFIG = OrderedDict(
    (
        (
            "STATION_NAME",
            (
                "Crazy Arms Radio Station",
                "The name of your radio station.",
                "station_name",
            ),
        ),
        (
            "PLAYOUT_LOG_PURGE_DAYS",
            (
                14,
                "The number of days to keep playout log entries after which they're purged. "
                "Set to 0 to keep playout log entries forever.",
                "positive_int",
            ),
        ),
        (
            "APPEND_LIVE_ON_STATION_NAME_TO_METADATA",
            (
                True,
                'Append the string "LIVE on <Station Name>" to the stream\'s metadata for live broadcasts.',
            ),
        ),
        (
            "HARBOR_COMPRESSION_NORMALIZATION",
            (True, "Enable compression and normalization on harbor stream."),
        ),
        (
            "HARBOR_TRANSITION_SECONDS",
            (
                2.5,
                "Fadeout time in seconds when transitioning between harbor sources. Set to 0 for no fadeout.",
                "positive_float",
            ),
        ),
        (
            "HARBOR_TRANSITION_WITH_SWOOSH",
            (
                False,
                "Transition between harbor sources with a ~1 second swoosh effect.",
            ),
        ),
        (
            "HARBOR_SWOOSH_AUDIO_FILE",
            (
                False,
                "Audio file for the swoosh (if enabled). Should be short, ie under 3-4 seconds.",
                "clearable_file",
            ),
        ),
        (
            "HARBOR_MAX_SECONDS_SILENCE_BEFORE_INVACTIVE",
            (
                15,
                "The maximum number of seconds of silence on a live source "
                "(eg. Zoom or live DJs) until it will be considered inactive, "
                "ie until we would treat it as if it were offline.",
                "nonzero_positive_int",
            ),
        ),
        (
            "HARBOR_FAILSAFE_AUDIO_FILE",
            (
                False,
                "Failsafe audio file that the harbor should play if there's nothing else to stream.",
                "clearable_file",
            ),
        ),
        (
            "HARBOR_TEST_ENABLED",
            (
                False,
                "Enable test harbor server",
            ),
        ),
        (
            "HARBOR_TEST_MASTER_PASSWORD",
            ("default", "Master password to access the test harbor server", "required_char"),
        ),
        (
            "UPSTREAM_FAILSAFE_AUDIO_FILE",
            (
                False,
                "Failsafe audio file that should be broadcast to upstream servers if we "
                "can't connect to the harbor, ie the harbor failed to start.",
                "clearable_file",
            ),
        ),
        ("AUTODJ_ENABLED", (True, "Whether or not to run an AutoDJ on the harbor.")),
        (
            "AUTODJ_REQUESTS",
            (
                "disabled",
                "AutoDJ requests enabled for the following users.",
                "autodj_requests_choices",
            ),
        ),
        (
            "AUTODJ_REQUESTS_NUM",
            (
                5,
                "The maximum number of pending AutoDJ requests (if enabled)",
                "nonzero_positive_int",
            ),
        ),
        (
            "AUTODJ_STOPSETS_ENABLED",
            (
                False,
                "Whether or not the AutoDJ plays stop sets (for ADs, PSAs, Station IDs, etc)",
            ),
        ),
        (
            "AUTODJ_STOPSETS_ONCE_PER_MINUTES",
            (
                20,
                mark_safe("How often a stop set should <em>approximately</em> be played (in minutes)"),
                "positive_int",
            ),
        ),
        (
            "AUTODJ_PLAYLISTS_ENABLED",
            (True, "Whether or not the AutoDJ should use playlists"),
        ),
        (
            "AUTODJ_ANTI_REPEAT_ENABLED",
            (
                True,
                "Whether or not the AutoDJ should attempt its anti-repeat algorithm. Note if "
                "you have too few tracks, this won't work.",
            ),
        ),  # unneeded if artists+tracks=0
        (
            "AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT",
            (
                50,
                "Number of tracks to avoid to avoid repeating (if possible). Set to 0 to disable.",
                "positive_int",
            ),
        ),
        (
            "AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST",
            (
                15,
                "Number of tracks to avoid playing the same artist (if possible). Set to 0 to disable.",
                "positive_int",
            ),
        ),
        (
            "ASSET_ENCODING",
            (
                "mp3",
                "Encoding of downloaded external assets and non-standard input files.",
                "asset_encoding_choices",
            ),
        ),
        (
            "ASSET_BITRATE",
            (
                "128K",
                "Bitrate (quality) of downloaded external and non-standard audio files. (Unused for FLAC.)",
                "asset_bitrate_choices",
            ),
        ),
        (
            "ASSET_DEDUPING",
            (
                True,
                "Enable duplicate detection for audio assets based on metadata and audio fingerprint.",
            ),
        ),
        (
            "GOOGLE_CALENDAR_ENABLED",
            (False, "Enabled Google Calendar based authentication for DJs."),
        ),
        ("GOOGLE_CALENDAR_ID", ("example@gmail.com", "Google Calendar ID.", "char")),
        (
            "GOOGLE_CALENDAR_CREDENTIALS_JSON",
            (
                "",
                mark_safe(
                    "Past the contents of your Google Service JSON Account Key here (a"
                    " <code>credentials.json</code> file).For more info from Google about this please <a"
                    ' href="https://cloud.google.com/docs/authentication/getting-started"'
                    ' target="_blank">click here</a>.'
                ),
            ),
        ),
    )
)

CONSTANCE_CONFIG_FIELDSETS = OrderedDict(
    (
        ("General Options", ("STATION_NAME", "PLAYOUT_LOG_PURGE_DAYS", "APPEND_LIVE_ON_STATION_NAME_TO_METADATA")),
        (
            "AutoDJ Configuration",
            (
                "AUTODJ_ENABLED",
                "AUTODJ_REQUESTS",
                "AUTODJ_REQUESTS_NUM",
                "AUTODJ_ANTI_REPEAT_ENABLED",
                "AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT",
                "AUTODJ_ANTI_REPEAT_NUM_TRACKS_NO_REPEAT_ARTIST",
                "AUTODJ_PLAYLISTS_ENABLED",
                "AUTODJ_STOPSETS_ENABLED",
                "AUTODJ_STOPSETS_ONCE_PER_MINUTES",
            ),
        ),
        (
            "Harbor Configuration",
            (
                "HARBOR_COMPRESSION_NORMALIZATION",
                "HARBOR_TRANSITION_WITH_SWOOSH",
                "HARBOR_SWOOSH_AUDIO_FILE",
                "HARBOR_TRANSITION_SECONDS",
                "HARBOR_MAX_SECONDS_SILENCE_BEFORE_INVACTIVE",
                "HARBOR_FAILSAFE_AUDIO_FILE",
                "UPSTREAM_FAILSAFE_AUDIO_FILE",
            ),
        ),
        (
            "Test Harbor Configuration",
            (
                "HARBOR_TEST_ENABLED",
                "HARBOR_TEST_MASTER_PASSWORD",
            ),
        ),
        (
            "Audio Assets Configuration",
            ("ASSET_ENCODING", "ASSET_BITRATE", "ASSET_DEDUPING"),
        ),
        (
            "Google Calendar Based Authentication",
            (
                "GOOGLE_CALENDAR_ENABLED",
                "GOOGLE_CALENDAR_ID",
                "GOOGLE_CALENDAR_CREDENTIALS_JSON",
            ),
        ),
    )
)

if ZOOM_ENABLED:
    CONSTANCE_CONFIG.update(
        OrderedDict(
            (
                (
                    "ZOOM_MAX_SHOW_LENTH_MINUTES",
                    (
                        5 * 60,
                        mark_safe("Maximum show length (in minutes) of an <em>unscheduled</em> Zoom broadcast."),
                        "zoom_minutes",
                    ),
                ),
                (
                    "ZOOM_DEFAULT_SHOW_LENTH_MINUTES",
                    (
                        2 * 60,
                        mark_safe(
                            "Default show length (in minutes) of an <em>unscheduled</em> Zoom broadcast. Note"
                            " shows scheduled through Google Calendar will default to the length of the"
                            " calendar event (or the maximum show length above, whichever is shorter)."
                        ),
                        "zoom_minutes",
                    ),
                ),
            )
        )
    )
    CONSTANCE_CONFIG_FIELDSETS.update(
        OrderedDict(
            (
                (
                    "Zoom Settings",
                    ("ZOOM_MAX_SHOW_LENTH_MINUTES", "ZOOM_DEFAULT_SHOW_LENTH_MINUTES"),
                ),
            )
        )
    )

if ICECAST_ENABLED:
    CONSTANCE_CONFIG.update(
        OrderedDict(
            (
                (
                    "ICECAST_LOCATION",
                    ("The World", "Location setting for the Icecast server.", "char"),
                ),
                (
                    "ICECAST_ADMIN_EMAIL",
                    (
                        f"admin@{DOMAIN_NAME}",
                        "The admin email setting for the Icecast server.",
                        "email",
                    ),
                ),
                (
                    "ICECAST_ADMIN_PASSWORD",
                    (
                        "default",
                        "Admin password for the Icecast server.",
                        "required_char",
                    ),
                ),
                (
                    "ICECAST_SOURCE_PASSWORD",
                    (
                        "default",
                        "Source password for the Icecast server.",
                        "required_char",
                    ),
                ),
                (
                    "ICECAST_RELAY_PASSWORD",
                    (
                        "default",
                        "Relay password for the Icecast server.",
                        "required_char",
                    ),
                ),
                (
                    "ICECAST_MAX_CLIENTS",
                    (
                        0,
                        "Max connected clients allowed the Iceacst server (0 for unlimited).",
                        "positive_int",
                    ),
                ),
                (
                    "ICECAST_MAX_SOURCES",
                    (
                        0,
                        "Max sources allowed to connect to the Icecast server (0 for unlimited).",
                        "positive_int",
                    ),
                ),
            )
        )
    )
    CONSTANCE_CONFIG_FIELDSETS.update(
        OrderedDict(
            (
                (
                    "Local Icecast Server Settings",
                    (
                        "ICECAST_LOCATION",
                        "ICECAST_ADMIN_EMAIL",
                        "ICECAST_ADMIN_PASSWORD",
                        "ICECAST_SOURCE_PASSWORD",
                        "ICECAST_RELAY_PASSWORD",
                        "ICECAST_MAX_CLIENTS",
                        "ICECAST_MAX_SOURCES",
                    ),
                ),
            )
        )
    )
