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
SSE_MESSAGE_URL = 'http://sse:8000/message'
REDIS_KEY = 'liquidsoap:source-status'


def json_of_mixed(~strs=[], ~bools=[], ~ints=[])
    json = [json_of(strs), json_of(bools), json_of(ints)]
    json = list.filter(fun(j) -> not string.match(pattern='^\\s*\\[\\s+\\]\\s*$', j), json)
    json = list.map(fun(j) -> list.assoc(default='"invalid": true', "1",
                                         string.extract(pattern='^\\s*\\{\\s*(.+?)\\s*\\}\\s*', j)), json)
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

# DJ Authentication
last_authorized_user = ref ('unknown', -1)
def dj_auth(username, password)
    data = json_of([('username', username), ('password', password)])
    url = '#{API_PREFIX}auth/'
    let ((_, status_code, _), _, response) = http.post(url, headers=API_HEADERS, data=data)
    if status_code != 200 then
        log('ERROR: got non-200 status got API (#{status_code}) for user #{username}')
        false
    else
        authorized =  list.assoc(default=false, 'authorized', of_json(default=[('authorized', false)], response))
        log('dj_auth: authorize with API for user #{username} returned: #{string_of(authorized)}')
        if authorized then
            user = list.assoc(default='unknown', 'user', of_json(default=[('user', 'unknown')], response))
            user_id = list.assoc(default=-1, 'user_id', of_json(default=[('user_id', -1)], response))
            last_authorized_user := (user, user_id)
        end
        authorized
    end
end

live_user = ref ('unknown', -1)
def dj_connect(headers)
    live_user := !last_authorized_user
end

def dj_disconnect()
    last_authorized_user := ('unknown', -1)
    live_user := ('unknown', -1)
end

### BEGIN SECTION 1 OF CUSTOM USER SOURCE CODE ###
{{ section1 }}
#### END SECTION 1 OF CUSTOM USER SOURCE CODE ####

dj_harbor = audio_to_stereo(
    id='dj_harbor_to_stereo',
    input.harbor('/stream', id='dj_harbor', port=8001, auth=dj_auth, on_connect=dj_connect,
                 on_disconnect=dj_disconnect, buffer=BUFFER, max=MAX))
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

failsafe = single(id='failsafe', '/assets/hold-music.mp3')

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

# Server status stuff
def status_json()
    active_sources = list.filter(fun(src) -> source.is_ready(snd(src)), source_hierarchy)
    streaming_source_id = list.hd(default='unknown', list.map(fun(src) -> source.id(snd(src)), active_sources))
    '[' ^ string.concat(separator=', ', list.mapi(fun(i, src) -> begin
        let (name, source) = src
        source_id = source.id(source)
        source_active = source.is_ready(source)
        current_stream = streaming_source_id == source_id
        let (user, user_id) = !live_user
        # TODO: live user should be based on connection, and callbacks on_connection on on_disconnect
        #       then each source should just have a bool called is_dj_harbor or something
        #       finally, sources should be a list in a dict, and dj_harbor should be abother nested
        #       dict with all the live information, ie kickoff time, connect time, etc
        let (json_strs, json_ints, json_bools) = if source_id == source.id(dj_harbor) and user_id != -1 then
            ([('id', source_id), ('name', name), ('user', user)],
             [('precedence', i + 1), ('user_id', user_id)],
             [('active', source_active), ('current_stream', current_stream)])
        else
            ([('id', source_id), ('name', name)],
             [('precedence', i + 1)],
             [('active', source_active), ('current_stream', current_stream), ('user', false), ('user_id', false)])
        end
        json_of_mixed(strs=json_strs, ints=json_ints, bools=json_bools)
    end, source_hierarchy)) ^ ']'
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
add_timeout(2.5, fun() -> begin update_status(); -1. end)

# Register callbacks on start/stop of all sources for push notifications
# XXX: is there a better way to do this?
list.map(fun(src) -> output.dummy(fallible=true, on_start=update_status, on_stop=update_status, snd(src)),
         source_hierarchy)

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

# TODO: add compressoin/normalization config option, like AzuraCast's

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
