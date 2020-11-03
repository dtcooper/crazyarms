set('server.telnet', true)
set('server.telnet.port', {{ TELNET_PORT }})
set('server.telnet.bind_addr', '0.0.0.0')
set('server.timeout', -1.)

url = 'http://harbor:4000/live'

input = input.http(id='input', max=10., poll_delay=0.5, url)
output.dummy(input, fallible=true)

failsafe = single(id='failsafe', '/assets/failsafe.mp3')
broadcast = fallback(track_sensitive=false, [input, failsafe])

output.icecast(
    %mp3(bitrate=128),
    id='broadcast',
    icy_metadata='true',
    host='{{ HOST }}',
    port={{ PORT }},
    password='{{ PASSWORD }}',
    mount='{{ MOUNT }}',
    broadcast,
)
