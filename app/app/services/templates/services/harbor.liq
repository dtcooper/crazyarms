{% load services %}

SCRIPT_NAME = 'harbor'
%include "library.liq"

set('server.telnet', true)
set('server.telnet.port', 1234)
set('server.telnet.bind_addr', '0.0.0.0')
set('server.timeout', -1.)
set('scheduler.fast_queues', 2)
set('scheduler.generic_queues', 4)

API_HEADERS = [('X-CARB-Secret-Key', {{ settings.SECRET_KEY|liqval:False }})]
API_PREFIX = 'http://app:8000/api/'
BUFFER = 5.
FAILSAFE_SOURCE_NAME = 'Failsafe Audio'
MAX = 10.
MAX_SILENCE = float_of_int({{ config.HARBOR_MAX_SECONDS_SILENCE_BEFORE_TRANSITION|liqval }})
REDIS_KEY = 'liquidsoap:source-status'
{% if config.AUTODJ_ENABLED %}
    REQUEST_QUEUE_LENGTH = 45.
    REQUEST_RETRY_DELAY = 5.
    REQUEST_TIMEOUT = 30.
{% endif %}
SSE_MESSAGE_URL = 'http://sse:3000/message'
STATION_NAME = {{ config.STATION_NAME|liqval }}
{% if config.HARBOR_TRANSITION_SECONDS %}
    TRANSITION_SECONDS = {{ config.HARBOR_TRANSITION_SECONDS|liqval }}
{% endif %}

start_time = time()

current_source_name := FAILSAFE_SOURCE_NAME

### Additional library functions

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

def is_infinity(f)
    int_of_float(f) == 0 and abs(f) > 1.
end

skippable_sources = ref []
def add_skip_command_carb(source)
    skippable_sources := list.add(source.id(source), !skippable_sources)
    add_skip_command(source)
end

def string_of_metadata(metadata)
    title = list.map(fun(key) -> metadata[key], ['artist', 'album', 'title'])
    title = string.concat(separator=' - ', list.filter(fun(val) -> val != '', title))
    if title == '' then
        'Untitled Track'
    else
        title
    end
end

# DJ Authentication
# (username, full_name, kickoff_time, user_id)
last_authorized_user = ref ('', '', -1., 0)
def dj_auth(username, password)
    data = json_of(compact=true, [('username', username), ('password', password)])
    url = '#{API_PREFIX}dj-auth/'
    let ((_, status_code, _), _, response) = http.post(url, headers=API_HEADERS, data=data)
    if status_code == 200 then
        authorized = list.assoc(default=false, 'authorized', of_json(default=[('_', false)], response))
        log('dj_auth: authorize with API for user #{username} returned: #{string_of(authorized)}')
        if authorized then
            full_name = list.assoc(default='', 'full_name', of_json(default=[('_', '')], response))
            json_ints = of_json(default=[('_', 0)], response)
            kickoff_time = float_of_int(list.assoc(default=-1, 'kickoff_time', json_ints))
            user_id = list.assoc(default=0, 'user_id', json_ints)
            last_authorized_user := (username, full_name, kickoff_time, user_id)
        end
        authorized
    else
        log('ERROR: dj_auth: got non-200 status got API (#{status_code}) for user #{username}')
        false
    end
end

# (username, full_name, kickoff_time, user_id, connection_time)
live_user_connected = ref false
live_user = ref ('', '', -1., 0, -1.)
status_update_ref = ref fun() -> ()  # requires dj_harbor to be defined
dj_harbor_insert_metadata_ref = ref fun(~new_track=false, m) -> ()
def dj_connect(headers)
    live_user_connected := true
    let (username, full_name, kickoff_time, user_id) = !last_authorized_user
    log_event(type=EVENT_LIVE_DJ, '#{username} authorized on the harbor', extras=[('user_id', string_of(user_id))])
    live_user := (username, full_name, kickoff_time, user_id, time())
    dj_harbor_insert_metadata = !dj_harbor_insert_metadata_ref
    # TODO: log show name if we have it
    dj_harbor_insert_metadata(new_track=true, [('title', '#{full_name} LIVE on #{STATION_NAME}')])
    status_update = !status_update_ref
    status_update()
end

def dj_disconnect()
    if !live_user_connected then
        let (username, _, _, user_id, _) = !live_user
        log_event(type=EVENT_LIVE_DJ, '#{username} disconnected from harbor', extras=[('user_id', string_of(user_id))])
        last_authorized_user := ('', '', -1., 0)
        live_user_connected := false
        live_user := ('', '', -1., 0, -1.)
        status_update = !status_update_ref
        status_update()
    end
end

add_timeout(fast=false, 2.5, fun() -> begin
    if !live_user_connected then
        let (username, full_name, kickoff_time, user_id, _) = !live_user
        # 1.5s of clearance so the DJ doesn't immediately re-auth
        if kickoff_time > 0. and time() - 1.5 > kickoff_time then
            log('kicking off #{username} for streaming past kickoff time')
            log_event(type=EVENT_LIVE_DJ, '#{username} kicked off for streaming past authorization bounds',
                      extras=[('user_id', string_of(user_id))])
            ignore(server.execute('dj_harbor.stop'))
        end
    end
    2.5
end)

### BEGIN SECTION 1 OF CUSTOM USER SOURCE CODE ###
{{ section1 }}
#### END SECTION 1 OF CUSTOM USER SOURCE CODE ####

dj_harbor = audio_to_stereo(
    id='dj_harbor_to_stereo',
    input.harbor('/stream', id='dj_harbor', port=8001, auth=dj_auth, on_connect=dj_connect,
                 on_disconnect=dj_disconnect, buffer=BUFFER, max=MAX))

let (dj_harbor_insert_metadata, dj_harbor) = insert_metadata(dj_harbor)
dj_harbor_insert_metadata_ref := dj_harbor_insert_metadata
dj_harbor_insert_metadata(new_track=true, [])

ignore(output.dummy(id='dj_harbor_dummy', dj_harbor, fallible=true))
dj_harbor = strip_blank(
    id='dj_harbor_strip',
    max_blank=MAX_SILENCE,
    start_blank=true,
    dj_harbor,
)

{% if settings.ZOOM_ENABLED %}
    zoom = input.pulseaudio(id='zoom')
    ignore(output.dummy(id='zoom_dummy', zoom))

    zoom = strip_blank(
        max_blank=MAX_SILENCE,
        id='zoom_strip',
        start_blank=true,
        min_noise=0.5,
        zoom,
    )
    zoom = map_metadata(update=false, strip=true, fun(_) -> begin
        # TODO hit redis for show name
        [('title', 'Live Broadcast')]
    end, zoom)
{% endif %}

prerecord = request.queue(id='prerecord')
prerecord = audio_to_stereo(id='prerecord_to_stereo', prerecord)
prerecord = on_end(id='prerecord_onend', delay=0., fun(_, _) -> begin
    status_update = !status_update_ref
    status_update()
end, prerecord)
add_skip_command_carb(prerecord)

{% if config.AUTODJ_ENABLED %}
    autodj = request.dynamic.list(
        # TODO: conservative always keeps one request in the queue, useful for skipping but
        # means station ID + could come several minutes afterwards. I think this is needed
        # so we don't transition to fallback all the time from autoDJ, but double check.
        id='autodj', conservative=false, length=REQUEST_QUEUE_LENGTH,
        retry_delay=REQUEST_RETRY_DELAY, timeout=REQUEST_TIMEOUT, fun() -> begin
            url = '#{API_PREFIX}next-track/'
            let ((_, status_code, _), _, response) = http.get(url, headers=API_HEADERS)
            if status_code == 200 then
                if list.assoc(default=false, 'has_audio_asset', of_json(default=[('_', false)], response)) then
                    audio_asset_uri = list.assoc(default='', 'audio_asset_uri', of_json(default=[('_', '')], response))
                    log('autodj: selected URI #{audio_asset_uri}')
                    [request.create(audio_asset_uri)]
                else
                    log('ERROR: autodj returned no track')
                    []
                end
            else
                log('ERROR: autodj: got non-200 status got API (#{status_code}) for next track')
                []
            end
        end)

    autodj = audio_to_stereo(id='autodj_to_stereo', autodj)
    autodj = on_end(id='autodj_onend', delay=0., fun(_, _) -> begin
        status_update = !status_update_ref
        status_update()
    end, autodj)

    # Having autodj safe for a few seconds means resolution loading files won't
    # transition to failsafe and just have a few seconds of silence
    add_skip_command_carb(autodj)
{% endif %}

failsafe = single(id='failsafe', '/assets/hold-music.mp3')

# If you add a source that has timed tracks, they should be added to this list
timed_sources = [prerecord{% if config.AUTODJ_ENABLED %}, autodj{% endif %}]

# You can add to these using custom code, see below
source_hierarchy = [
    (prerecord, 'Prerecorded Broadcast'),
    (dj_harbor, 'Live DJ'),
{% if settings.ZOOM_ENABLED %}
    (zoom, 'Zoom Room'),
{% endif %}
{% if config.AUTODJ_ENABLED %}
    (autodj, 'AutoDJ'),
{% endif %}
    (failsafe, FAILSAFE_SOURCE_NAME)
]

#
# To add a source,
#  * Make sure it's fallible unless this is a design choice, possibly by strip_blank()
#  * Insert it into hierarchy, (possibly list.insert() above)
#  * Example below for a secondary DJ,
#
#>>>    secondary_harbor = audio_to_stereo(input.harbor(
#>>>        '/secondary', port=8001, password='topsecret', buffer=BUFFER, max=MAX))
#>>>    output.dummy(secondary_harbor, fallible=true)
#
#  * And then redefine the source_hierarchy,
#
#>>>    source_hierarchy = [...from above, (secondary_harbor, 'Secondary DJ'), ...from above]
#

### BEGIN SECTION 2 OF CUSTOM USER SOURCE CODE ###
{{ section2 }}
#### END SECTION 2 OF CUSTOM USER SOURCE CODE ####

source_hierarchy_lookups = list.map(fun(s) -> (source.id(fst(s)), snd(s)), source_hierarchy)

# Server status stuff
current_metadata = ref []
def status_json()
    active_sources = list.filter(fun(src) -> source.is_ready(fst(src)), source_hierarchy)
    streaming_source_id = list.hd(default='unknown', list.map(fun(src) -> source.id(fst(src)), active_sources))
    sources = '[' ^ string.concat(separator=',', list.mapi(fun(n, src) -> begin
        let (source, name) = src
        id = source.id(source)
        json_of_mixed_types(
            strs=[('id', id), ('name', name)], ints=[('precedence', n + 1)],
            bools=[('is_active', source.is_ready(source)), ('is_current_stream', id == streaming_source_id)])
    end, source_hierarchy)) ^ ']'

    live_user = if !live_user_connected then
        let (username, full_name, kickoff_time, user_id, connected_since) = !live_user
        let (user_nulls, user_floats) = if kickoff_time > 0. then
            ([], [('connected_since', connected_since), ('kickoff_time', kickoff_time)])
        else
            (['kickoff_time'], [('connected_since', connected_since)])
        end

        json_of_mixed_types(strs=[('username', username), ('full_name', full_name)], ints=[('user_id', user_id)],
                            floats=user_floats, nulls=user_nulls)
    else
        'null'
    end

    now = time()
    timed = list.map(fun(s) -> begin
        remaining = source.remaining(s)
        # int_of_float covers weird infinity case, truncating it to zero
        remaining = if remaining > 0. and not is_infinity(remaining) then now + remaining else -1. end
        (source.id(s), remaining)
    end, timed_sources)
    timed = json_of(compact=true, list.filter(fun(s) -> snd(s) > -1., timed))

    skippable = json_of(compact=true, !skippable_sources)
    dj_harbor_source = json_of(compact=true, source.id(dj_harbor))
    metadata = json_of(compact=true, !current_metadata)
    server_info = json_of_mixed_types(floats=[('start_time', start_time)], strs=[('version', liquidsoap.version)])

    '{"sources":#{sources},"dj_harbor_source":#{dj_harbor_source},"live_user":#{live_user},'
        ^ '"skippable_sources":#{skippable},"timed_sources":#{timed},"metadata":#{metadata},'
        ^ '"server_info": #{server_info}}'
end
server.register(usage='status', description='Get status of sources in JSON', 'status', fun(_) -> status_json())
server.register(usage='status_pretty', description='Get status of sources in JSON (pretty-printed)', 'status_pretty',
                fun(_) -> get_process_output(env=[('JSON', status_json())], 'echo "$JSON" | python3 -m json.tool --sort-keys'))

def update_status()
    # Do this asynchronously (0.05 to give things time to settle.)
    add_timeout(fast=false, 0.25, fun() -> begin
        status = status_json()
        cmd = 'redis-cli -h redis set "liquidsoap:status" "$STATUS"'
        log('update_status: updating redis key: #{REDIS_KEY} (step 1/2)')
        if not test_process(env=[('STATUS', status)], cmd) then
            log.severe('ERROR: failed to update redis key: #{REDIS_KEY} (cmd = #{cmd} / json = #{status})')
        end
        log('update_status: hitting sse service (step 2/2)')
        let ((_, status_code, _), _, _) = http.post(SSE_MESSAGE_URL, data=status)
        if status_code != 204 then
            log.severe('ERROR: failed to update sse service, expected status code 204 (got #{status_code})')
        end
        -1.
    end)
end
status_update_ref := update_status
add_timeout(fast=false, 2.5, fun() -> begin update_status(); -1. end)
server.register(usage='status_update', description='Force a status update push to web clients', 'status_update', fun(_) -> begin
    update_status()
    'Done!'
end)

# Register callbacks on start/stop of all sources for push notifications
ignore(list.map(fun(src) -> begin
    source = fst(src)
    output.dummy(id='#{source.id(source)}_callback_dummy', fallible=true,
                 on_start=update_status, on_stop=update_status, source)
    end, source_hierarchy))

# Radio playout
{% if config.HARBOR_TRANSITION_WITH_SWOOSH %}
    swoosh = single('/assets/transition.mp3')
{% endif %}
def transition(~source, one, two)
    last_source_name = !current_source_name
    current_source_name := list.assoc(default='Unknown', source.id(source), source_hierarchy_lookups)
    log('Transitioning to #{source.id(source)} [#{source.id(one)} -> #{source.id(two)}]')
    log_event(type=EVENT_SOURCE_TRANSITION, 'Transitioned from #{last_source_name} to #{!current_source_name}')

    {% if config.AUTODJ_ENABLED %}
        two = if source.id(source) == source.id(autodj) and source.id(one) != source.id(failsafe) then
            source.skip(autodj)
            # Avoid metadata duplication by sequencing after 50ms
            sequence([blank(duration=0.05), two])
        else
            two
        end
    {% endif %}

    {% if not config.HARBOR_TRANSITION_SECONDS and not config.HARBOR_TRANSITION_WITH_SWOOSH %}
        two
    {% else %}
        add(normalize=false, [
            two,
            {% if config.HARBOR_TRANSITION_WITH_SWOOSH %}
                once(swoosh),
            {% endif %}
            {% if config.HARBOR_TRANSITION_SECONDS %}
                fade.final(duration=TRANSITION_SECONDS, one),
            {% endif %}
        ])
    {% endif %}
end

radio = fallback(
    id='radio',
    replay_metadata=false,
    track_sensitive=false,
    transitions=list.map(fun(src) -> transition(source=fst(src)), source_hierarchy),
    list.map(fun(src) -> fst(src), source_hierarchy),
)

### BEGIN SECTION 3 OF CUSTOM USER SOURCE CODE ###
{{ section3 }}
#### END SECTION 3 OF CUSTOM USER SOURCE CODE ####

radio = on_metadata(fun(m) -> begin
    update_status()

    if !current_source_name == FAILSAFE_SOURCE_NAME then
        log_event(type=EVENT_TRACK, 'Played failsafe audio track')
    else
        audio_asset_id = m['audio_asset_id']
        metadata = metadata.export(m)

        let (metadata, extras) = if audio_asset_id == '' then
            (metadata, [])
        else
            (list.add(('audio_asset_id', audio_asset_id), metadata), [('audio_asset_id', audio_asset_id)])
        end

        current_metadata := metadata
        log_event(type=EVENT_TRACK, string_of_metadata(metadata), extras=extras)
    end
end, radio)

{% if config.HARBOR_COMPRESSION_NORMALIZATION %}
    log('Enabling output compression and normalization.')
    radio = normalize(target=0., window=0.03, gain_min=-16., gain_max=0., compress.exponential(radio, mu=1.))
{% endif %}

output.harbor(
    %wav(duration=0., stereo=true, channels=2, samplesize=16, header=true),
    id='broadcast',
    mount='live',
    port=4000,
    radio,
)
