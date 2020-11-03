import json

import asyncio
from aiohttp import web
from aiohttp_sse import sse_response

# Dead simple server-sent event (SSE) server. No authentication, no frills.
# Server is protected by nginx's "internal" flag and authenticated by Django
# and an X-Accel-Redirect
#
# GET:/ -- subscribes to messages
# POST:/message -- sends a message to all subscribers
#


class MessageListener:
    def __init__(self):
        self.event = asyncio.Event()
        self.message = {}
        self.queue = asyncio.Queue()
        self.task = asyncio.create_task(self._task())

    async def _task(self):
        while True:
            self.message = json.dumps(await self.queue.get())
            try:
                self.event.set()
                self.event.clear()
            finally:
                self.queue.task_done()

    async def done(self):
        await self.queue.join()
        self.task.cancel()


async def start_message_listener(app):
    app['messages'] = MessageListener()


async def cancel_message_listener(app):
    await app['messages'].done()


async def subscribe(request):
    listener = request.app['messages']
    async with sse_response(request) as resp:
        while True:
            await listener.event.wait()
            if listener.message == '{"message": "quit"}':
                break
            await resp.send(listener.message)
    return resp


async def message(request):
    message = await request.json()
    request.app['messages'].queue.put_nowait(message)
    return web.Response(status=204)


async def test(response):
    html = """
        <html>
        <body>
            <script>
                var evtSource = new EventSource("/")
                var received = 0
                evtSource.onmessage = function(e) {
                    received += 1
                    var message = (new Date()) + ': ' + JSON.stringify(JSON.parse(e.data), null, 2) + "\\n\\n"
                    var elem = document.getElementById('response')
                    elem.innerText = message + elem.innerText
                    document.getElementById('received').innerText = received
                }
            </script>
            <h1>Messages: <span id="received">0</span> received</h1>
            <pre id="response"></pre>
        </body>
        </html>
        """
    return web.Response(text=html, content_type='text/html')


application = web.Application()
application.router.add_route('GET', '/', subscribe)
application.router.add_route('POST', '/message', message)
application.router.add_route('GET', '/test', test)
application.on_startup.append(start_message_listener)
application.on_shutdown.append(cancel_message_listener)

if __name__ == '__main__':
    web.run_app(application, host='0.0.0.0', port=3000)
