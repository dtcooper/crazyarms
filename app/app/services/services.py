import logging
import os
import shutil
import subprocess

from django.conf import settings
from django.core.cache import cache
from django.template.context import make_context
from django.template.loader import get_template

from constance import config

from carb import constants


logger = logging.getLogger(f'carb.{__name__}')

SUPERVISOR_RUNNING_STATES = {'STARTING', 'RUNNING', 'BACKOFF'}


class ServiceBase:
    supervisor_enabled = True

    def __init__(self):
        self._server = None
        self.programs_to_start = []

    def render_conf(self):
        raise NotImplementedError()

    def supervisorctl(self, *args):
        cmd = ['supervisorctl', '-s', f'http://{self.service_name}:9001'] + list(args)
        logger.info(f'running: {" ".join(cmd)}')
        cmd = subprocess.run(cmd, capture_output=True, text=True)
        if cmd.returncode != 0:
            logger.warning(f'supervisorctl exited with {cmd.returncode}')

        stdout, stderr = (' / '.join(s.strip().splitlines()) for s in (cmd.stdout, cmd.stderr))
        if stderr:
            logger.warning(f'supervisorctl error output: {stderr}')
        if stdout:
            logger.info(f'supervisorctl output: {stdout}')

        return stdout

    def render_conf_file(self, filename, context=None, conf_filename=None):
        default_context = {'settings': settings, 'config': config}
        if context is not None:
            default_context.update(context)

        template = get_template(f'services/{filename}')
        conf = template.template.render(make_context(default_context, autoescape=False))

        conf_filename = f'/config/{self.service_name}/{filename if conf_filename is None else conf_filename}'
        os.makedirs(os.path.dirname(conf_filename), exist_ok=True)
        with open(conf_filename, 'w') as conf_file:
            conf_file.write(conf)
            logger.info(f'writing config file {conf_filename}')

    def clear_supervisor_conf(self):
        shutil.rmtree(f'/config/{self.service_name}/supervisor', ignore_errors=True)

    def render_supervisor_conf_file(self, command, program_name=None, start=True, **extras):
        program_name = self.service_name if program_name is None else program_name
        self.render_conf_file('service.conf', conf_filename=f'supervisor/{program_name}.conf', context={
            'command': command,
            'program': program_name,
            'extras': extras,
        })

        if start:
            self.programs_to_start.append(program_name)

    def reload_supervisor(self, restart_services=False):
        if self.supervisor_enabled:
            if restart_services:
                self.supervisorctl('stop', 'all')

            self.supervisorctl('update')

            if self.programs_to_start:
                self.supervisorctl('start', *self.programs_to_start)


class IcecastService(ServiceBase):
    supervisor_enabled = False
    service_name = 'icecast'

    def render_conf(self):
        self.render_conf_file('icecast.xml')


class HarborService(ServiceBase):
    CUSTOM_CONFIG_NUM_SECTIONS = 3
    service_name = 'harbor'

    def render_conf(self):
        from .models import PlayoutLogEntry

        self.render_conf_file('library.liq', context={
            'playout_log_entry_table_name': PlayoutLogEntry._meta.db_table,
            'event_types': zip(PlayoutLogEntry.EventType.names, PlayoutLogEntry.EventType.values)})
        self.render_conf_file('harbor.liq', context=cache.get(constants.CACHE_KEY_HARBOR_CONFIG_CONTEXT))
        kwargs = {'environment': 'HOME="/tmp/pulse"', 'user': 'liquidsoap'}

        liq_cmd = 'liquidsoap /config/harbor/harbor.liq'
        if settings.ZOOM_ENABLED:
            # Wait for pulse to be up
            self.render_supervisor_conf_file(command=f'sh -c "wait-for-it -t 0 localhost:4713 && {liq_cmd}"', **kwargs)
            self.render_supervisor_conf_file(
                # TODO is auth-ip-acl needed?
                # TODO: log source/sink connections
                command='pulseaudio -n --load="module-native-protocol-tcp auth-ip-acl=127.0.0.1 auth-anonymous=1" '
                        '--load=module-native-protocol-unix --load=module-always-sink --exit-idle-time=-1',
                program_name='pulseaudio', **kwargs)
        else:
            self.render_supervisor_conf_file(command=liq_cmd, **kwargs)


class UpstreamService(ServiceBase):
    service_name = 'upstream'

    def render_conf(self):
        from .models import PlayoutLogEntry, UpstreamServer

        # Make sure there's a local Icecast upstream
        local_icecast = UpstreamServer.objects.filter(name='local-icecast')
        if settings.ICECAST_ENABLED:
            if not local_icecast.exists():
                UpstreamServer.objects.create(
                    name='local-icecast',  # Special read-only name
                    hostname='icecast',
                    port=8000,
                    username='source',
                    mount='live',
                )
            local_icecast.update(password=config.ICECAST_SOURCE_PASSWORD)
        else:
            local_icecast.delete()

        if UpstreamServer.objects.exists():
            self.render_conf_file('library.liq', context={
                'playout_log_entry_table_name': PlayoutLogEntry._meta.db_table,
                'event_types': zip(PlayoutLogEntry.EventType.names, PlayoutLogEntry.EventType.values)})

        for upstream in UpstreamServer.objects.all():
            self.render_conf_file('upstream.liq', conf_filename=f'{upstream.name}.liq', context={'upstream': upstream})
            self.render_supervisor_conf_file(command=f'liquidsoap /config/upstream/{upstream.name}.liq',
                                             program_name=upstream.name, user='liquidsoap')


class ZoomService(ServiceBase):
    service_name = 'zoom'

    # TODO move to ServiceBase with name as arg, and provide @cached_property version
    def is_zoom_running(self):
        status = self.supervisorctl('status', 'zoom-runner').split()
        return len(status) >= 2 and status[1] == 'RUNNING'

    def render_conf(self):
        kwargs = {'environment': f'TZ="{settings.TIME_ZONE}",HOME="/home/user",DISPLAY=":0",PULSE_SERVER="harbor"',
                  'user': 'user'}

        # Windowing manager and VNC
        self.render_supervisor_conf_file(
            program_name='xvfb-icewm',
            command='xvfb-run --auth-file=/home/user/.Xauthority --server-num=0 '
                    "--server-args='-screen 0 1250x875x16' icewm-session",
            **kwargs
        )
        self.render_supervisor_conf_file(
            program_name='x11vnc', command='x11vnc -shared -forever -nopw', **kwargs)
        self.render_supervisor_conf_file(
            program_name='websockify', command='websockify 0.0.0.0:6080 localhost:5900', **kwargs)

        # Zoom and the room runner script
        self.render_supervisor_conf_file(
            program_name='zoom', command='sh -c "killall -q zoom; zoom"', start=False, **kwargs)
        self.render_supervisor_conf_file(program_name='zoom-runner', command='zoom-runner.sh', start=False)


SERVICES = {service_cls.service_name: service_cls for service_cls in ServiceBase.__subclasses__()}

if not settings.ICECAST_ENABLED:
    del SERVICES[IcecastService.service_name]
if not settings.ZOOM_ENABLED:
    del SERVICES[ZoomService.service_name]


def init_services(services=None, restart_services=False, subservices=(), render_only=False):
    if isinstance(services, str):
        services = (services,)

    if not services:
        services = SERVICES.keys()

    for service in services:
        logger.info(f'initializing service: {service}{" (rendering only)" if render_only else ""}')
        service_cls = SERVICES[service]
        service = service_cls()

        if service.supervisor_enabled:
            service.clear_supervisor_conf()

        service.render_conf()

        if service.supervisor_enabled and not render_only:
            service.reload_supervisor(restart_services=restart_services)

            if subservices:
                if isinstance(subservices, str):
                    subservices = (subservices,)
                service.supervisorctl('restart', *subservices)
