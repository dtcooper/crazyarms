from django.core.management.base import BaseCommand, CommandError

from carb.models import ScheduledGCalShow

from constance import config


class Command(BaseCommand):
    help = 'Sync scheduled shows with Google Calendar'

    def handle(self, *args, **options):
        if not config.GCAL_AUTH_ENABLED:
            raise CommandError('Google Calendar based authentication disabled')

        ScheduledGCalShow.sync_with_gcal()
