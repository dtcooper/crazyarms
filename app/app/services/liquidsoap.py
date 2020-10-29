from telnetlib import Telnet
from threading import Lock

END_PREFIX = b'\r\nEND\r\n'


class LiquidsoapTelnetException(Exception):
    pass


class _Liquidsoap:
    def __init__(self, host='harbor', port=1234):
        self._telnet = None
        self._telnet_access_lock = Lock()
        self._version = None
        self.host = host
        self.port = port

    @property
    def version(self):
        if self._version is None:
            try:
                self._version = self.execute('version').removeprefix('Liquidsoap ')
            except LiquidsoapTelnetException:
                return 'unknown'
        return self._version

    def execute(self, command, arg=None, splitlines=None):
        if arg is not None:
            command += f' {arg}'
        command = f'{command}\n'.encode('utf-8')

        with self._telnet_access_lock:
            try:
                if self._telnet is None:
                    self._telnet = Telnet(host=self.host, port=self.port)

                self._telnet.write(command)
                response = self._telnet.read_until(END_PREFIX)
            except Exception as e:
                self._telnet = None
                raise LiquidsoapTelnetException(str(e))

        response = response.removesuffix(END_PREFIX).decode('utf-8').splitlines()
        return response if splitlines else '\n'.join(response)

    def __getattr__(self, command):
        command = command.replace('__', '.')
        return lambda arg=None, splitlines=None: self.execute(command, arg, splitlines)


harbor = _Liquidsoap()
