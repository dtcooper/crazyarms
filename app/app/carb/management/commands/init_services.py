from django.core.management.base import BaseCommand

from .models import User
from carb.services import init_services


class Command(BaseCommand):
    help = 'Initialize CARB Services'

    def add_arguments(self, parser):
        parser.add_argument('services', nargs='*', type=str, help='list of services to start (default: all)', default=None)
        parser.add_argument('-r', '--restart', action='store_true', help='force a restart of the services')
        parser.add_argument('-f', '--force', action='store_true', help='always run')

    def handle(self, *args, **options):
        if User.objects.exists() or options['force']:
            if options['services']:
                self.stdout.write(f'Initializing services ({", ".join(options["services"])})')
            else:
                self.stdout.write('Initializing services (all)')

            init_services(services=options['services'], restart_services=options['restart'])
        else:
            self.stdout.write('No users exists, assuming this is the first run and not starting services')
