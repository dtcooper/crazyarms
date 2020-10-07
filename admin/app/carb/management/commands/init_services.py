from django.core.management.base import BaseCommand

from carb.services import HarborService, IcecastService


class Command(BaseCommand):
    help = 'Initialize CARB Services'
    services = {
        'harbor': HarborService,
        'icecast': IcecastService,
    }

    def add_arguments(self, parser):
        parser.add_argument('services', nargs='*', type=str, help='list of services to start (default: all)')
        parser.add_argument('-r', '--restart', action='store_true', help='force a restart of the services')

    def handle(self, *args, **options):
        self.stdout.write('Initializing services:', ending='')
        self.stdout.flush()

        for service_name in (options['services'] or self.services.keys()):
            service = self.services[service_name]()
            service.generate_conf()
            service.reload_supervisor(restart_services=options['restart'])
            self.stdout.write(f' {service_name}', ending='')
            self.stdout.flush()

        self.stdout.write('... done!')
