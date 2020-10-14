from telnetlib import Telnet

END_PREFIX = b'\r\nEND\r\n'


class Liquidsoap:
    def __init__(self, host='harbor', port=1234):
        self._telnet = None
        self.host = host
        self.port = port

    def __getattr__(self, command):
        command = command.replace('__', '.')

        def func(arg=None, splitlines=False):
            if self._telnet is None:
                self._telnet = Telnet(host=self.host, port=self.port)

            to_execute = command
            if arg is not None:
                to_execute += f' {arg}'
            to_execute += '\n'
            self._telnet.write(to_execute.encode('utf-8'))
            response = self._telnet.read_until(END_PREFIX).removesuffix(END_PREFIX).decode('utf-8').splitlines()
            return response if splitlines else '\n'.join(response)
        return func
