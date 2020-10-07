from django.conf import settings as django_settings

from constance import config as constance_config


def settings(request):
    return {'settings': django_settings, 'config': constance_config}
