from django.core.management.base import BaseCommand, CommandError

from carb.services import IcecastService


class Command(BaseCommand):
    help = 'Initialize CARB Services'
    services = {
        'icecast': IcecastService,
    }

    def add_arguments(self, parser):
        parser.add_argument('services', nargs='*', type=str, help='List of services to start (default: all)')

    def handle(self, *args, **options):
        for service_name in (options['services'] or self.services.keys()):
            service = self.services[service_name]()
            service.generate_config()
            service.reload_supervisor()
