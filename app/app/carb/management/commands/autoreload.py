import shlex
import subprocess

from django.core.management.base import BaseCommand
from django.utils import autoreload


def restart_celery():
    cmd = 'pkill -f "celery worker"'
    subprocess.call(shlex.split(cmd))
    cmd = 'celery worker -A django_celery_example --loglevel=info'
    subprocess.call(shlex.split(cmd))


class Command(BaseCommand):
    help = "Autoreload a command when project's Python files change"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pid = None

    def add_arguments(self, parser):
        parser.add_argument('command', nargs='*', type=str, help='command to autoreload', default=None)

    def

    def handle(self, *args, **options):
        print('Starting celery worker with autoreload...')

        # For Django>=2.2
        #autoreload.run_with_reloader(restart_celery)
        print(f'args: {args!r}')
        print(f'opts: {options!r}')

        # For django<2.1
        # autoreload.main(restart_celery)
