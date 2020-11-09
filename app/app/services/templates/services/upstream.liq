{% load services %}

set('server.telnet', true)
set('server.telnet.port', {{ upstream.telnet_port|liquidsoap_value }})
set('server.telnet.bind_addr', '0.0.0.0')
set('server.timeout', -1.)

url = 'http://harbor:4000/live'

input = input.http(id='input', max=10., poll_delay=0.5, url)
output.dummy(input, fallible=true)

failsafe = single(id='failsafe', '/assets/failsafe.mp3')
broadcast = fallback(track_sensitive=false, [input, failsafe])

host = {{ upstream.hostname|liquidsoap_value }}
user = {{ upstream.username|liquidsoap_value }}
password = {{ upstream.password|liquidsoap_value }}
mount = {{ '/'|add:upstream.mount|liquidsoap_value }}
name = {{ upstream.name|liquidsoap_value }}
log('Starting upstream "#{name}"')

output.icecast(
    %{{ upstream.encoding }}(
        {# TODO implement upstream.encoding_args #}
        {% if upstream.bitrate %}bitrate={{ upstream.bitrate }},{% endif %}
    ),
    id='broadcast',
    icy_metadata='true',
    host=host,
    port={{ upstream.port|liquidsoap_value }},
    user=user,
    password=password,
    mount=mount,
    broadcast,
)
