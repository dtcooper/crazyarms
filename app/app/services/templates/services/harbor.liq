set('server.telnet', true)
set('server.telnet.port', 1234)
set('server.telnet.bind_addr', '0.0.0.0')
set('server.timeout', -1.)

# Safely rendered environment variables based on configuration.
%include "harbor.vars.liq"

BUFFER = 5.
MAX = 10.
API_HEADERS = [('X-CARB-Secret-Key', SECRET_KEY)]
API_PREFIX = 'http://app:8000/api/'

def json_of_mixed(~strs=[], ~bools=[], ~ints=[])
    json = [json_of(strs), json_of(bools), json_of(ints)]
    json = list.filter(fun(j) -> not string.match(pattern='^\\s*\\[\\s+\\]\\s*$', j), json)
    json = list.map(fun(j) -> list.assoc(default='"invalid": true', "1", string.extract(pattern='^\\s*\\{\\s*(.+?)\\s*\\}\\s*', j)), json)
    json = string.concat(separator=', ', json)
    '{#{json}}'
end

def list.insert(index, new_element, l) =
  if index == 0 then
    list.add(new_element, l)
  else
    def f(cur, el) =
      let (pos, l) = cur
      l = if pos+1 == index then
          list.add(new_element, list.add(el, l))
        else
          list.add(el, l)
        end
      (pos+1, l)
    end
    let (_, l) = list.fold(f, (0, []), l)
    list.rev(l)
  end
end

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

### BEGIN SECTION 1 OF CUSTOM USER SOURCE CODE ###
{{ section1 }}
#### END SECTION 1 OF CUSTOM USER SOURCE CODE ####

dj_harbor = audio_to_stereo(
    id='dj_harbor_to_stereo',
    input.harbor(
        '/stream',
        id='dj_harbor',
        port=8001,
        auth=dj_auth,
        buffer=BUFFER,
        max=MAX,
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

prerecord = request.equeue(id='prerecord')
add_skip_command(prerecord)

failsafe = single(id='failsafe', '/hold-music.mp3')

source_hierarchy = [
      # TODO switch from equeue to queue? Rename id?
    ('Prerecorded Broadcast', prerecord),
    ('Live DJ', dj_harbor),
{% if settings.ZOOM_ENABLED %}
    ('Zoom Room', zoom),
{% endif %}
    ('Failsafe Audio', failsafe)
]

#
# To add a source,
#  * Make sure it's fallible unless this is a design choice, possibly by strip_blank()
#  * Insert it into hierarchy, (possibly list.insert() above)
#  * Example below for a secondary DJ
#
#    secondary_dj_harbor = audio_to_stereo(input.harbor(
#        '/secondary', port=8001, password='topsecret', buffer=BUFFER, max=MAX))
#    output.dummy(secondary_dj_harbor, fallible=true)
#    # Insert after dj_harbor
#    source_hierarchy = list.insert(2, ('Secondary DJ', secondary_dj_harbor), source_hierarchy)

### BEGIN SECTION 2 OF CUSTOM USER SOURCE CODE ###
{{ section2 }}
#### END SECTION 2 OF CUSTOM USER SOURCE CODE ####

def transition(~source, one, two)
    log('Transitioning to #{source.id(source)} [#{source.id(one)} -> #{source.id(two)}')
    two
end

server.register(usage='source_status', description='Get status of all sources', 'source_status', fun (_) -> begin
    active_sources = list.filter(fun(src) -> source.is_ready(snd(src)), source_hierarchy)
    current_source = list.hd(default='unknown', list.map(fun(src) -> source.id(snd(src)), active_sources))
    sources_json = '[' ^ string.concat(separator=', ', list.mapi(fun(i, src) -> json_of_mixed(
        strs=[('id', source.id(snd(src))), ('name', fst(src))],
        ints=[('precedence', i + 1)],
        bools=[('active', source.is_ready(snd(src)))]),
    source_hierarchy)) ^ ']'
    '{"sources": #{sources_json}, "active_source": #{json_of(current_source)}}'
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
