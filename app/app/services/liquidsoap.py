import json
import logging
from telnetlib import Telnet
from threading import Lock

END_PREFIX = b"\r\nEND\r\n"

logger = logging.getLogger(f"crazyarms.{__name__}")


class LiquidsoapTelnetException(Exception):
    pass


class _Liquidsoap:
    MAX_TRIES = 3

    def __init__(self, host="harbor", port=1234):
        self._telnet = None
        # Since huey runs as threaded, let's make sure only one thread actually talks to
        # the telnet connection at a given time.
        self._access_lock = Lock()
        self._version = None
        self.host = host
        self.port = port

    @property
    def version(self):
        if self._version is None:
            try:
                self._version = self.execute("version").removeprefix("Liquidsoap ")
            except LiquidsoapTelnetException:
                return "unknown"
        return self._version

    def execute(self, command, arg=None, splitlines=False, safe=False, as_dict=False):
        if arg is not None:
            command += f" {arg}"
        command = f"{command}\n".encode("utf-8")

        with self._access_lock:
            for try_number in range(self.MAX_TRIES):  # Try three times before giving up
                try:
                    if self._telnet is None:
                        self._telnet = Telnet(host=self.host, port=self.port)

                    self._telnet.write(command)
                    response = self._telnet.read_until(END_PREFIX)
                    break
                except Exception as e:
                    self._telnet = None
                    if try_number >= self.MAX_TRIES - 1:
                        if safe:
                            return None
                        else:
                            raise LiquidsoapTelnetException(str(e))

        response = response.removesuffix(END_PREFIX).decode("utf-8").splitlines()
        if as_dict or not splitlines:
            response = "\n".join(response)
            if as_dict:
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    logger.warning(f"Error decoding liquidsoap json: {response}")
                    if safe:
                        return None
                    else:
                        raise

        return response

    def __getattr__(self, command):
        command = command.replace("__", ".")
        return lambda arg=None, **kwargs: self.execute(command=command, arg=arg, **kwargs)


class _UpstreamGetter:
    def __init__(self):
        self.upstream_liquidsoaps = {}

    def __call__(self, upstream):
        port = upstream.telnet_port
        liquidsoap = self.upstream_liquidsoaps.get(port)
        if not liquidsoap:
            liquidsoap = self.upstream_liquidsoaps[port] = _Liquidsoap(host="upstream", port=port)
        return liquidsoap


harbor = _Liquidsoap()
upstream = _UpstreamGetter()
