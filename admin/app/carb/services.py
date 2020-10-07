import os
from xmlrpc.client import ServerProxy

from django.conf import settings
from django.template.loader import render_to_string


class CarbServiceBase:
    service_name = None

    def __init__(self):
        self._server = None
        self.services_to_start = []
        self.services_to_stop = []

    def generate_config(self):
        raise NotImplementedError()

    @property
    def server(self):
        if self._server is None:
            self._server = ServerProxy(f'http://{self.service_name}:9001/RPC2')
        return self._server

    def render_config(self, filename, context=None, config_filename=None):
        default_context = {'settings': settings}
        if context is not None:
            default_context.update(context)

        config = render_to_string(f'services/{filename}', context=default_context)

        config_filename = f'/config/{self.service_name}/{filename if config_filename is None else config_filename}'
        os.makedirs(os.path.dirname(config_filename), exist_ok=True)
        with open(config_filename, 'w') as config_file:
            config_file.write(config)

    def render_supervisor_config(self, command, service_name=None, start=False, **extras):
        service_name = self.service_name if service_name is None else service_name
        context = {
            'command': command,
            'program': service_name,
            'autostart': start,
            'extras': extras,
        }

        self.render_config('service.conf', config_filename=f'supervisor/{service_name}.conf', context=context)
        if start:
            self.services_to_start.append(service_name)
        else:
            self.services_to_stop.append(service_name)

    def reload_supervisor(self):
        print(f'reloading {self.service_name}')
        self.server.supervisor.reloadConfig()


class IcecastService(CarbServiceBase):
    service_name = 'icecast'

    def generate_config(self):
        self.render_config('icecast.xml')
        self.render_supervisor_config(command='icecast -c /etc/icecast.xml', user='icecast', start=True)


class HarborService(CarbServiceBase):
    service_name = 'harbor'

    def generate_config(self):
        self.render_config('harbor.liq')
        self.render_supervisor_config(command='liquidsoap /etc/liquidsoap/harbor.liq', user='liquidsoap', start=True)
