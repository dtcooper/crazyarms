# flake8: noqa

import fakeredis

from django_redis.pool import ConnectionFactory

from .settings import *


# We use django-redis's features like `cache.key(...)` and `cache.ttl(...)`
# at times, so we need to stub it out with fakeredis. See,
# https://github.com/jamesls/fakeredis/issues/234#issuecomment-465131855
class FakeDjangoRedisConnectionFactory(ConnectionFactory):
    def get_connection(self, params):
        return self.redis_client_cls(**self.redis_client_cls_kwargs)


DJANGO_REDIS_CONNECTION_FACTORY = "crazyarms.settings_test.FakeDjangoRedisConnectionFactory"
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "REDIS_CLIENT_CLASS": "fakeredis.FakeStrictRedis",
        },
    }
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}


HUEY["immediate"] = True
del HUEY["connection"]
