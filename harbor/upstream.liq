%include "common.liq"

DJ_MASTER_PASSWORD = conf('DJ_MASTER_PASSWORD')
INTERNAL_HARBOR_PORT = conf('INTERNAL_HARBOR_PORT')
ICECAST_UPSTREAM_NAME =  conf('ICECAST_UPSTREAM_NAME')

input = input.http(
    id='input',
    max=conf_float('INPUT_MAX'),
    poll_delay=0.5,
    'http://user:#{DJ_MASTER_PASSWORD}@localhost:#{INTERNAL_HARBOR_PORT}/broadcast?upstream=#{ICECAST_UPSTREAM_NAME}',
)
output.dummy(input, fallible=true)

failsafe = single(id='failsafe', conf('FAILSAFE_PATH'))
broadcast = fallback(track_sensitive=false, [input, failsafe])

if conf('ICECAST_BROADCAST_TYPE') != 'mp3' then
    error('Only mp3 supported at this time')
end

output.icecast(
    %mp3(bitrate=128),
    id='broadcast',
    host=conf('ICECAST_BROADCAST_HOST'),
    port=conf_int('ICECAST_BROADCAST_PORT'),
    password=conf('ICECAST_BROADCAST_PASSWORD'),
    mount=conf('ICECAST_BROADCAST_MOUNT'),
    url=conf('ICECAST_BROADCAST_URL'),
    description=conf('ICECAST_BROADCAST_DESCRIPTION'),
    genre=conf('ICECAST_BROADCAST_GENRE'),
    broadcast,
)
