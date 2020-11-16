# flake8: noqa

from .settings import *


DATABASES['default']['HOST'] = 'db_test'
CACHES['default']['LOCATION'] = 'redis://redis_test'

HUEY['immediate'] = True
del HUEY['connection']
