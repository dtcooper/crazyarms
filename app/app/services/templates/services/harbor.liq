set('server.telnet', true)
set('server.telnet.port', 1234)
set('server.telnet.bind_addr', '0.0.0.0')
set('server.timeout', -1.)
set('scheduler.fast_queues', 1)

# Safely rendered environment variables based on configuration.
%include "harbor.vars.liq"

BUFFER = 5.
MAX = 10.
API_HEADERS = [('X-CARB-Secret-Key', SECRET_KEY)]
API_PREFIX = 'http://app:8000/api/'
SSE_MESSAGE_URL = 'http://sse:3000/message'
REDIS_KEY = 'liquidsoap:source-status'


def json_of_mixed_types(~strs=[], ~bools=[], ~ints=[], ~floats=[], ~nulls=[])
    json = [json_of(compact=true, strs), json_of(compact=true, bools),
            json_of(compact=true, ints), json_of(compact=true, floats)]
    json = list.filter(fun(j) -> j != '[]' and j != '{}', json)
    json = list.map(fun(j) -> list.assoc(default='!INVALID REGEX!', '1',
                                         string.extract(pattern='^\\{(.+?)\\}', j)), json)
    json = list.append(json, list.map(fun(s) -> '#{json_of(s)}:null', nulls))
    json = string.concat(separator=',', json)
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

# DJ Authentication
# (username, full_name, user_id)
last_authorized_user = ref ('', '', 0)
def dj_auth(username, password)
    data = json_of([('username', username), ('password', password)])
    url = '#{API_PREFIX}auth/'
    let ((_, status_code, _), _, response) = http.post(url, headers=API_HEADERS, data=data)
    if status_code != 200 then
        log('ERROR: got non-200 status got API (#{status_code}) for user #{username}')
        false
    else
        authorized =  list.assoc(default=false, 'authorized', of_json(default=[('_', false)], response))
        log('dj_auth: authorize with API for user #{username} returned: #{string_of(authorized)}')
        if authorized then
            user_id = list.assoc(default=0, 'user_id', of_json(default=[('_', 0)], response))
            full_name = list.assoc(default='', 'full_name', of_json(default=[('_', '')], response))
            last_authorized_user := (username, full_name, user_id)
        end
        authorized
    end
end

# (username, full_name, user_id, connection_time)
live_user_connected = ref false
live_user = ref ('', '', 0, -1.)
dj_status_update_callback = ref fun() -> ()  # requires dj_harbor to be defined
def dj_connect(headers)
    live_user_connected := true
    let (username, full_name, user_id) = !last_authorized_user
    live_user := (username, full_name, user_id, time())
    status_update = !dj_status_update_callback
    status_update()
end

def dj_disconnect()
    last_authorized_user := ('', '', 0)
    live_user_connected := false
    live_user := ('', '', 0, -1.)
    status_update = !dj_status_update_callback
    status_update()
end

### BEGIN SECTION 1 OF CUSTOM USER SOURCE CODE ###
{{ section1 }}
#### END SECTION 1 OF CUSTOM USER SOURCE CODE ####

dj_harbor = audio_to_stereo(
    id='dj_harbor_to_stereo',
    input.harbor('/stream', id='dj_harbor', port=8001, auth=dj_auth, on_connect=dj_connect,
                 on_disconnect=dj_disconnect, buffer=BUFFER, max=MAX))
ignore(output.dummy(id='dj_harbor_dummy', dj_harbor, fallible=true))
dj_harbor = strip_blank(
    id='dj_harbor_strip',
    max_blank=15.,  # TODO: configurable
    start_blank=true,
    dj_harbor,
)

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

prerecord = request.queue(id='prerecord')
prerecord = audio_to_stereo(id='prerecord_to_stereo', prerecord)
add_skip_command(prerecord)

failsafe = single(id='failsafe', '/assets/hold-music.mp3')

# You can add to these using custom code, see below
source_hierarchy = [
    ('Prerecorded Broadcast', prerecord),
    ('Live DJ', dj_harbor),
{% if settings.ZOOM_ENABLED %}
    ('Zoom Room', zoom),
{% endif %}
    ('Failsafe Audio', failsafe)
]

# Add to these as well if needed to the status page UI
skippable_sources = [prerecord]
timed_sources = [prerecord]

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

# Server status stuff
def status_json()
    active_sources = list.filter(fun(src) -> source.is_ready(snd(src)), source_hierarchy)
    streaming_source_id = list.hd(default='unknown', list.map(fun(src) -> source.id(snd(src)), active_sources))
    sources = '[' ^ string.concat(separator=',', list.mapi(fun(n, src) -> begin
        let (name, source) = src
        id = source.id(source)
        json_of_mixed_types(
            strs=[('id', id), ('name', name)], ints=[('precedence', n + 1)],
            bools=[('is_active', source.is_ready(source)), ('is_current_stream', id == streaming_source_id)])
    end, source_hierarchy)) ^ ']'

    live_user = if !live_user_connected then
        let (username, full_name, user_id, connected_since) = !live_user
        json_of_mixed_types(strs=[('username', username), ('full_name', full_name)],
                            ints=[('user_id', user_id)], floats=[('connected_since', connected_since)])
    else
        'null'
    end

    now = time()
    timed = list.map(fun(s) -> begin
        remaining = source.remaining(s)
        remaining = if remaining > 0. then now + remaining else -1. end
        (source.id(s), remaining)
    end, timed_sources)
    timed = json_of(compact=true, list.filter(fun(s) -> snd(s) > -1., timed))

    skippable = json_of(compact=true, list.map(fun(s) -> source.id(s), skippable_sources))

    dj_harbor_source = json_of(compact=true, source.id(dj_harbor))

    '{"sources":#{sources},"dj_harbor_source":#{dj_harbor_source},"live_user":#{live_user},'
        ^ '"skippable_sources":#{skippable},"timed_sources":#{timed}}'
end
server.register(usage='status', description='Get status of sources', 'status', fun(_) -> status_json())

def update_status()
    # Do this asynchronously (0.05 to give things time to settle.)
    add_timeout(0.25, fun() -> begin
        status = status_json()
        cmd = "redis-cli -h redis set 'liquidsoap:status' #{string.quote(status)}"
        log('update_status: updating redis key: #{REDIS_KEY} (step 1/2)')
        if not test_process(cmd) then
            log('ERROR: failed to update redis key: #{REDIS_KEY} (cmd = #{cmd})')
        end
        log('update_status: hitting sse service (step 2/2)')
        let ((_, status_code, _), _, _) = http.post(SSE_MESSAGE_URL, data=status)
        if status_code != 204 then
            log('ERROR: failed to update sse service, expected status code 204 (got #{status_code})')
        end
        -1.
    end)
end
dj_status_update_callback := update_status
add_timeout(2.5, fun() -> begin update_status(); -1. end)
server.register('status_update', description='Force a status update to sse + redis', fun(_) -> begin
    update_status()
    'Done!'
end)

# Register callbacks on start/stop of all sources for push notifications
# XXX: is there a better way to do this?
ignore(list.map(fun(src) -> output.dummy(fallible=true, on_start=update_status, on_stop=update_status, snd(src)),
                source_hierarchy))

# Radio playout
swoosh = single('/assets/transition.mp3')
def transition(~source, one, two)
    log('Transitioning to #{source.id(source)} [#{source.id(one)} -> #{source.id(two)}')
    add(normalize=false, if TRANSITION_WITH_SWOOSH then
        [fade.final(duration=2.5, one), once(swoosh),  two]
    else
        [fade.final(duration=2.5, one), two]
    end)
end

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

radio = if COMPRESSION_NORMALIZATION then
    log('Enabling compression and normalization.')
    normalize(target=0., window=0.03, gain_min=-16., gain_max=0., compress.exponential(radio, mu=1.))
else
    radio
end

output.harbor(
    %wav(duration=0., stereo=true, channels=2, samplesize=16, header=true),
    id='broadcast',
    mount='live',
    port=4000,
    radio,
)
