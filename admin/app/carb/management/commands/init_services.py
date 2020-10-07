from django.core.management.base import BaseCommand

from carb.services import HarborService, IcecastService


class Command(BaseCommand):
    help = 'Initialize CARB Services'
    services = {
        'harbor': HarborService,
        'icecast': IcecastService,
    }

    def add_arguments(self, parser):
        parser.add_argument('services', nargs='*', type=str, help='List of services to start (default: all)')

    def handle(self, *args, **options):
        self.stdout.write('Initializing services:', ending='')
        self.stdout.flush()

        for service_name in (options['services'] or self.services.keys()):
            service = self.services[service_name]()
            service.generate_config()
            service.reload_supervisor()
            self.stdout.write(f' {service_name}', ending='')
            self.stdout.flush()

        self.stdout.write('... done!')
