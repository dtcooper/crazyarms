%include "common.liq"

set('server.telnet', conf_bool('UPSTREAM_TELNET_ENABLE'))
set('server.telnet.port', conf_int('UPSTREAM_TELNET_PORT'))
if file.exists('/.dockerenv') then
    # Docker only! Otherwise always localhost.
    set('server.telnet.bind_addr', '0.0.0.0')
end

INTERNAL_HARBOR_PASSWORD = conf('INTERNAL_HARBOR_PASSWORD')
INTERNAL_HARBOR_PORT = conf('INTERNAL_HARBOR_PORT')
UPSTREAM_NAME =  conf('UPSTREAM_NAME')


input = input.http(
    id='input',
    max=conf_float('INPUT_MAX'),
    poll_delay=0.5,
    'http://user:#{INTERNAL_HARBOR_PASSWORD}@localhost:#{INTERNAL_HARBOR_PORT}/broadcast?upstream=#{UPSTREAM_NAME}',
)
output.dummy(input, fallible=true)

failsafe = single(id='failsafe', conf('FAILSAFE_PATH'))
broadcast = fallback(track_sensitive=false, [input, failsafe])

if conf('UPSTREAM_ICECAST_TYPE') != 'mp3' then
    error('Only mp3 supported at this time')
end

output.icecast(
    %mp3(bitrate=128),
    id='broadcast',
    host=conf('UPSTREAM_ICECAST_HOST'),
    port=conf_int('UPSTREAM_ICECAST_PORT'),
    password=conf('UPSTREAM_ICECAST_PASSWORD'),
    mount=conf('UPSTREAM_ICECAST_MOUNT'),
    url=conf('UPSTREAM_ICECAST_URL'),
    description=conf('UPSTREAM_ICECAST_DESCRIPTION'),
    genre=conf('UPSTREAM_ICECAST_GENRE'),
    broadcast,
)
