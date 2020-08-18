def error(s)
    print(s)
    log(s)
    exit(1)
end

def conf(name, ~allow_empty=false)
    value = getenv(name)
    if not allow_empty and value == '' then
        error('Configuration value "' ^ name ^ ' not set. Consider running with '
              ^ '"./run.sh" to set environment. Shutting down.')
    end
    value
end

def conf_int(name)
    int_of_string(conf(name))
end

def conf_float(name)
    float_of_string(conf(name))
end

def conf_bool(name)
    value = string.case(string.trim(conf(allow_empty=true, name)))
    not (value == '' or value == 'false' or value == 'f' or value == '0')
end

set('server.telnet', conf_bool('TELNET_ENABLE'))
set('server.telnet.port', conf_int('TELNET_PORT'))

DJ_MASTER_PASSWORD = conf('DJ_MASTER_PASSWORD')
dj_harbor = input.harbor(
    conf('DJ_MOUNT_NAME'),
    id='dj_harbor',
    port=conf_int('DJ_PORT'),
    auth=fun(user, pass) -> pass == DJ_MASTER_PASSWORD,
    max=conf_float('INPUT_MAX'),
    buffer=conf_float('INPUT_BUFFER'),
)
output.dummy(dj_harbor, id='dj_harbor_dummy', fallible=true)

dj_harbor = strip_blank(
    max_blank=conf_float('DJ_MAX_SILENCE'),
    id='dj_harbor_strip',
    start_blank=true,
    audio_to_stereo(id='dj_audio_to_stereo', dj_harbor),
)

pulse_in = input.pulseaudio()
output.dummy(id='pulse_in', pulse_in)

pulse_in = strip_blank(
    max_blank=conf_float('PULSE_MAX_SILENCE'),
    id='pulse_in_strip',
    start_blank=true,
    pulse_in,
)

autodj = playlist.safe(conf('AUTO_DJ_SIMPLE_FOLDER'))  # TODO: make more complicated

CROSSFADE_TIMER = conf_float('CROSSFADE_TIMER')
current_stream = ref source.id(autodj)  # assume lowest precedence in fallback
def crossfade(~source, one, two)
    log('Transitioning to #{source.id(source)} [#{source.id(one)} -> #{source.id(two)}]')
    current_stream := source.id(source)
    add(normalize=false, [
        sequence([
            blank(duration=CROSSFADE_TIMER),
            fade.initial(duration=CROSSFADE_TIMER, two)
        ]),
        fade.final(duration=CROSSFADE_TIMER * 2., one)
    ])
end

radio_fallback_precedence = [dj_harbor, pulse_in, autodj]
radio = fallback(
    id='radio',
    track_sensitive=false,
    transitions=list.map(fun(s) -> crossfade(source=s), radio_fallback_precedence),
    radio_fallback_precedence,
)

radio = if conf_bool('OUTPUT_COMPRESSOR_ENABLE') then
    log('Enabling output compressor')
    nrj(radio)
else
    radio
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
    radio,
)
