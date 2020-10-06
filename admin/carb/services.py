import os
from xmlrpc.client import ServerProxy

from django.conf import settings
from django.template.loader import render_to_string


class CarbServiceBase:
    service_name = None

    def render_config(self, filename, context=None, config_filename=None):
        default_context = {'settings': settings}
        if context is not None:
            default_context.update(context)

        config = render_to_string(f'services/{filename}', context=default_context)

        config_filename = f'/config/{self.service_name}/{filename if config_filename is None else config_filename}'
        os.makedirs(os.path.dirname(config_filename), exist_ok=True)
        with open(config_filename, 'w') as config_file:
            config_file.write(config)

    def reload_supervisor(self):
        server = ServerProxy(f'http://{self.service_name}:9001/RPC2')
        server.supervisor.reloadConfig()


class IcecastService(CarbServiceBase):
    service_name = 'icecast'

    def generate_config(self):
        self.render_config('icecast.xml')
        self.render_config('service.conf',  config_filename='supervisor/icecast.conf', context={
            'autostart': False,
            'command': 'icecast -c /etc/icecast.xml',
            'program': 'icecast',
            'user': 'icecast',
        })
