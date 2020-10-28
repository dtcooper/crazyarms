import pytz

from django.utils import timezone


class UserTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            tz = pytz.timezone(request.user.timezone)
            timezone.activate(tz)
        else:
            timezone.deactivate()
        return self.get_response(request)
