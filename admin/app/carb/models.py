from django.contrib.auth.models import User
from django.db import models


HARBOR_AUTH_NEVER = 'n'
HARBOR_AUTH_ALWAYS = 'a'
HARBOR_AUTH_SCHEDULE = 's'
HARBOR_AUTH_CHOICES = (
    (HARBOR_AUTH_ALWAYS, 'Always'),
    (HARBOR_AUTH_NEVER, 'Never'),
    (HARBOR_AUTH_SCHEDULE, 'Schedule Based'),
)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    harbor_auth = models.CharField(max_length=1, choices=HARBOR_AUTH_CHOICES)
