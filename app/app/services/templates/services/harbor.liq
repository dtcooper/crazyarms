set('server.telnet', true)
set('server.telnet.port', 1234)
set('server.telnet.bind_addr', '0.0.0.0')
set('server.timeout', -1.)

# Safely rendered environment variables based on configuration.
%include "harbor.vars.liq"

### BEGIN SECTION 1 OF CUSTOM USER SOURCE CODE ###
{{ section1 }}
#### END SECTION 1 OF CUSTOM USER SOURCE CODE ####

API_HEADERS = [('X-CARB-Secret-Key', SECRET_KEY)]
API_PREFIX = 'http://app:8000/api/'

def dj_auth(username, password)
    data = json_of([('username', username), ('password', password)])
    let ((_, status_code, _), _, response) = http.post('#{API_PREFIX}auth/', headers=API_HEADERS, data=data)
    if status_code != 200 then
        false
    else
        response = of_json(default=[('authorized', false)], response)
        list.assoc(default=false, 'authorized', response)
    end
end

dj_harbor = audio_to_stereo(
    id='dj_harbor_to_stereo',
    input.harbor(
        '/stream',
        id='dj_harbor',
        port=8001,
        auth=dj_auth,
        buffer=5.,
        max=10.,
    ),
)
ignore(output.dummy(id='dj_harbor_dummy', dj_harbor, fallible=true))

{% if settings.ZOOM_ENABLED %}
zoom = input.pulseaudio(id='zoom')
ignore(output.dummy(id='zoom_dummy', zoom))

zoom = strip_blank(
    max_blank=15.,  # TODO: make a constance
    id='zoom_strip',
    start_blank=true,
    min_noise=0.5,
    zoom,
)
{% endif %}

failsafe = single(id='failsafe', '/hold-music.mp3')

source_hierarchy = [
      # TODO switch from equeue to queue? Rename id?
    ('Prerecorded Broadcast', request.equeue(id='prerecorded')),
    ('Live DJ', dj_harbor),
{% if settings.ZOOM_ENABLED %}
    ('Zoom Room', zoom),
{% endif %}
    ('Failsafe Audio', failsafe),
]

# To add a source, make sure it's fallible (via strip blank?) add it to `source_hierarchy'
# list in the format of ("Pretty Name", source)

### BEGIN SECTION 2 OF CUSTOM USER SOURCE CODE ###
{{ section2 }}
#### END SECTION 2 OF CUSTOM USER SOURCE CODE ####

def transition(~source, one, two)
    log('Transitioning to #{source.id(source)} [#{source.id(one)} -> #{source.id(two)}')
    two
end

server.register(usage='source_status', description='Get status of all sources', 'source_status', fun (_) -> begin
    json_of(list.mapi(fun(i, src) ->
        [
            ('precedence', string_of(i + 1)), ('id', source.id(snd(src))),
            ('name', fst(src)), ('active', string_of(source.is_ready(snd(src))))
        ],
        source_hierarchy,
    ))
end)

radio = fallback(
    id='radio',
    replay_metadata=false,
    track_sensitive=false,
    transitions=list.map(fun(src) -> transition(source=snd(src)), source_hierarchy),
    list.map(fun(src) -> snd(src), source_hierarchy),
)

### BEGIN SECTION 3 OF CUSTOM USER SOURCE CODE ###
{{ section3 }}
#### END SECTION 3 OF CUSTOM USER SOURCE CODE ####

output.harbor(
    %wav(duration=0., stereo=true, channels=2, samplesize=16, header=true),
    id='broadcast',
    mount='stream',
    port=2817,
    radio,
)
