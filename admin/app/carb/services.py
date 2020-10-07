import os
from xmlrpc.client import ServerProxy

from django.conf import settings
from django.template.loader import render_to_string

from constance import config


class CarbServiceBase:
    service_name = None

    def __init__(self):
        self._server = None
        self.services_to_start = []
        self.services_to_stop = []

    def generate_conf(self):
        raise NotImplementedError()

    @property
    def server(self):
        if self._server is None:
            self._server = ServerProxy(f'http://{self.service_name}:9001/RPC2')
        return self._server

    def render_conf(self, filename, context=None, conf_filename=None):
        default_context = {'settings': settings, 'config': config}
        if context is not None:
            default_context.update(context)

        conf = render_to_string(f'services/{filename}', context=default_context)

        conf_filename = f'/config/{self.service_name}/{filename if conf_filename is None else conf_filename}'
        os.makedirs(os.path.dirname(conf_filename), exist_ok=True)
        with open(conf_filename, 'w') as conf_file:
            conf_file.write(conf)

    def render_supervisor_conf(self, command, service_name=None, start=False, **extras):
        service_name = self.service_name if service_name is None else service_name
        context = {
            'command': command,
            'program': service_name,
            'autostart': start,
            'extras': extras,
        }

        self.render_conf('service.conf', conf_filename=f'supervisor/{service_name}.conf', context=context)
        if start:
            self.services_to_start.append(service_name)
        else:
            self.services_to_stop.append(service_name)

    def reload_supervisor(self):
        self.server.supervisor.reloadConfig()


class IcecastService(CarbServiceBase):
    service_name = 'icecast'

    def generate_conf(self):
        self.render_conf('icecast.xml')
        self.render_supervisor_conf(
            command='icecast -c /etc/icecast.xml', user='icecast', start=config.ICECAST_ENABLED)


class HarborService(CarbServiceBase):
    service_name = 'harbor'

    def generate_conf(self):
        self.render_conf('harbor.liq')
        self.render_supervisor_conf(command='liquidsoap /etc/liquidsoap/harbor.liq', user='liquidsoap', start=True)
