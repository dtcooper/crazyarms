%include "common.liq"

set('server.telnet', conf_bool('UPSTREAM_TELNET_ENABLE'))
set('server.telnet.port', conf_int('UPSTREAM_TELNET_PORT'))
if file.exists('/.dockerenv') then
    # Docker only! Otherwise always localhost.
    set('server.telnet.bind_addr', '0.0.0.0')
end

password = conf('INTERNAL_HARBOR_PASSWORD')
port = conf('INTERNAL_HARBOR_PORT')
url = 'http://user:#{password}@localhost:#{port}/stream?upstream=#{script_name}'
log('Connecting to harbor URL: #{url}')
input = input.http(id='input', max=conf_float('INPUT_MAX'), poll_delay=0.5, url)
output.dummy(input, fallible=true)

failsafe = single(id='failsafe', conf('FAILSAFE_PATH'))
broadcast = fallback(track_sensitive=false, [input, failsafe])

encoding = conf('UPSTREAM_ICECAST_ENCODING')
log('Upstream "#{script_name}", encoding "#{encoding}"')

content_type = ref ""  # empty string to guess
format = (
    if encoding == 'aac-48' then
        content_type := 'audio/aacp'
        %fdkaac(bitrate=48, afterburner=true, sbr_mode=true)
    else
        if encoding != 'mp3-128' then
            error('Invalid encoding #{encoding}')
        end
        %mp3(bitrate=128)
    end
)


output.icecast(
    format,
    id='broadcast',
    format=!content_type,
    icy_metadata='true',
    host=conf('UPSTREAM_ICECAST_HOST'),
    port=conf_int('UPSTREAM_ICECAST_PORT'),
    password=conf('UPSTREAM_ICECAST_PASSWORD'),
    mount=conf('UPSTREAM_ICECAST_MOUNT'),
    url=conf('UPSTREAM_ICECAST_URL'),
    description=conf('UPSTREAM_ICECAST_DESCRIPTION'),
    genre=conf('UPSTREAM_ICECAST_GENRE'),
    broadcast,
)
