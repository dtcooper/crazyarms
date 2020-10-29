from telnetlib import Telnet
from threading import Lock

END_PREFIX = b'\r\nEND\r\n'


class LiquidsoapTelnetException(Exception):
    pass


class _Liquidsoap:
    def __init__(self, host='harbor', port=1234):
        self._telnet = None
        self._telnet_access_lock = Lock()
        self.host = host
        self.port = port

    def __getattr__(self, command):
        command = command.replace('__', '.')

        def func(arg=None, splitlines=False):
            to_execute = command
            if arg is not None:
                to_execute += f' {arg}'
            to_execute = f'{to_execute}\n'.encode('utf-8')

            with self._telnet_access_lock:
                try:
                    if self._telnet is None:
                        self._telnet = Telnet(host=self.host, port=self.port)

                    self._telnet.write(to_execute)
                    response = self._telnet.read_until(END_PREFIX)
                except Exception as e:
                    self._telnet = None
                    raise LiquidsoapTelnetException(str(e))

            response = response.removesuffix(END_PREFIX).decode('utf-8').splitlines()
            return response if splitlines else '\n'.join(response)
        return func


harbor = _Liquidsoap()
