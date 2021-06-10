{% load services %}

name = {{ upstream.name|liqval }}
SCRIPT_NAME = 'Upstream "#{name}"'
HEALTHCHECK_PORT = {{ upstream.healthcheck_port|liqval }}

%include "library.liq"

set('server.telnet', true)
set('server.telnet.port', {{ upstream.telnet_port|liqval }})

url = 'http://harbor:4000/live'

input = input.http(
    id='input',
    buffer=BUFFER,
    max=MAX,
    poll_delay=0.5,
    on_connect=fun(_) -> log_event('#{SCRIPT_NAME} connected to harbor'),
    on_disconnect=fun() -> log_event('#{SCRIPT_NAME} disconnected from harbor'),
    url,
)
output.dummy(input, fallible=true)

failsafe = single(id='failsafe',
{% if config.UPSTREAM_FAILSAFE_AUDIO_FILE %}
    {{ settings.MEDIA_ROOT|add:'/'|add:config.UPSTREAM_FAILSAFE_AUDIO_FILE|liqval }}
{% else %}
    '/assets/failsafe.mp3'
{% endif %}
)
broadcast = fallback(track_sensitive=false, [input, failsafe])

host = {{ upstream.hostname|liqval }}
user = {{ upstream.username|liqval }}
password = {{ upstream.password|liqval }}
mount = {{ '/'|add:upstream.mount|liqval }}
{% if upstream.mime %}
format = {{ upstream.mime|liqval }}
{% endif %}
log('Starting upstream "#{name}"')

connection_str = {{ upstream|liqval }}

UNKNOWN_ERROR_STR = 'Unknown error occurred (see upstream logs)'
connected = ref false
error = ref UNKNOWN_ERROR_STR
start_time = ref -1.

output.icecast(
    %{{ upstream.encoding }}(
{% if upstream.bitrate %}
        bitrate={{ upstream.bitrate }}{% if upstream.encoding_args %},{% endif %}
{% endif %}
{% if upstream.encoding_args %}
{% for arg, value in upstream.encoding_args.items %}
        {{ arg }}={{ value|liqval:False }}{% if not forloop.last %},{% endif %}
{% endfor %}
{% endif %}
    ),
    id='broadcast',
    icy_metadata='true',
    protocol='http{% if upstream.protocol == 'https' %}s{% endif %}',
{% if upstream.mime %}
    format=format,
{% endif %}
    host=host,
    port={{ upstream.port|liqval }},
    user=user,
    password=password,
    mount=mount,
    broadcast,
    on_connect=fun() -> begin
        connected := true
        log_event('#{SCRIPT_NAME} successfully connected to #{connection_str}')
        start_time := time()
        error := UNKNOWN_ERROR_STR
    end,
    on_disconnect=fun() -> begin
        connected := false
        log_event('#{SCRIPT_NAME} disconnected from #{connection_str}')
        error := UNKNOWN_ERROR_STR
    end,
    on_error=fun(e) -> begin
        if !error != e then
            log_event('#{SCRIPT_NAME} connection error to #{connection_str}: #{e}')
        end
        error := e
        1.  # Re-try connection every second
    end,
)

server.register(usage='status', description='Status of upstream connection', 'status', fun(_) -> begin
    error = if !error == "" then "null" else json_of(!error) end
    start_time = if !connected then json_of(!start_time) else 'null' end
    '{"online":#{json_of(!connected)},"error":#{error},"start_time":#{start_time}}'
end)
