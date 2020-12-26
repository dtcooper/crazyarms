from django.conf import settings

from .version import __version__


def carb_extra_context(request):
    return {'settings': settings, 'carb_version': __version__,
            # can_boot has no relevant admin page
            'user_has_admin_permissions': bool(request.user.get_all_permissions() - {'common.can_boot'})}
