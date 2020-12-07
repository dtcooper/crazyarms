{% load services %}

SCRIPT_NAME = 'Harbor'
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
LIVE_DJ_KICKOFF_INTERVAL = 5.
HARBOR_PORT = 8001
MAX = 10.
MAX_SILENCE = float_of_int({{ config.HARBOR_MAX_SECONDS_SILENCE_BEFORE_INVACTIVE|liqval }})
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

# Override from library.liq
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

# A complete hack
def is_infinity(f) int_of_float(f) == 0 and abs(f) > 1. end

# Track what sources we skip so we can serve that in status JSON
skippable_sources = ref []
def add_skip_command_carb(source)
    skippable_sources := list.add(source.id(source), !skippable_sources)
    add_skip_command(source)
end

# Override liquidsoap standard library function to make it Artist - Album - Track
def string_of_metadata(metadata)
    title = list.map(fun(key) -> metadata[key], ['artist', 'album', 'title'])
    title = string.concat(separator=' - ', list.filter(fun(val) -> val != '', title))
    if title == '' then
        'Untitled Track'
    else
        title
    end
end

# DJ authorization: hits api/views.py:
# last_authorized_user = (username, full_name, kickoff_time, user_id)
last_authorized_user = ref ('', '', -1., 0)
def dj_auth(username, password)
    data = json_of(compact=true, [('username', username), ('password', password)])
    url = '#{API_PREFIX}dj-auth/'
    let ((_, status_code, _), _, response) = http.post(url, headers=API_HEADERS, data=data)
    if status_code == 200 then
        authorized = list.assoc(default=false, 'authorized', of_json(default=[('_', false)], response))
        log('dj_auth: authorize with API for user #{username} returned: #{string_of(authorized)}')
        if authorized then
            # Parse out response and save to last_authorized_user
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

# Process internal state changes for dj connection and dj disconnection below

live_user_connected = ref false
# live_user = (username, full_name, kickoff_time, user_id, connection_time)
live_user = ref ('', '', -1., 0, -1.)

# Circular references, ie status_update and dj_harbor_insert_metadata, need to be defined below but called here
dj_harbor_insert_metadata_ref = ref fun(~new_track=false, m) -> ()  # requires dj_harbor to be defined

# Process DJ connection
def dj_connect(headers)
    live_user_connected := true

    # Get data saved from last call to dj_auth
    let (username, full_name, kickoff_time, user_id) = !last_authorized_user
    log_event(type=EVENT_LIVE_DJ, '#{username} authorized on the harbor', extras=[('user_id', string_of(user_id))])
    live_user := (username, full_name, kickoff_time, user_id, time())

    # Insert metadata about DJ (they can always override it via their client)
    dj_harbor_insert_metadata = !dj_harbor_insert_metadata_ref

    # TODO: log show name if we have it?
    dj_harbor_insert_metadata(new_track=true, [('title', '#{full_name} LIVE on #{STATION_NAME}')])
end

# Process DJ disconnect
def dj_disconnect()
    # Noticed multiple calls to on_disconnect, so make sure we process disconnection only once
    if !live_user_connected then
        live_user_connected := false

        let (username, _, _, user_id, _) = !live_user
        log_event(type=EVENT_LIVE_DJ, '#{username} disconnected from harbor', extras=[('user_id', string_of(user_id))])
        last_authorized_user := ('', '', -1., 0)
        live_user := ('', '', -1., 0, -1.)
    end
end

# Our "reaper" internal function
add_timeout(fast=false, LIVE_DJ_KICKOFF_INTERVAL, fun() -> begin
    if !live_user_connected then
        let (username, _, kickoff_time, user_id, _) = !live_user
        # 1.5s of buffer to be sure backend will refuse DJ in the event of immediately trying to log in again
        if kickoff_time > 0. and time() - 1.5 > kickoff_time then
            log('kicking off #{username} for streaming past kickoff time')
            log_event(type=EVENT_LIVE_DJ, '#{username} kicked off for streaming past authorization bounds',
                      extras=[('user_id', string_of(user_id))])
            ignore(server.execute('dj_harbor.stop'))
        end
    end
    LIVE_DJ_KICKOFF_INTERVAL
end)

reset_status = ("", "", "", "", "", "")
last_status_without_timed_sources = ref reset_status

### BEGIN SECTION 1 OF CUSTOM USER SOURCE CODE ###
{{ section1 }}
#### END SECTION 1 OF CUSTOM USER SOURCE CODE ####

# DJ harbor
dj_harbor = audio_to_stereo(
    id='dj_harbor_to_stereo',
    input.harbor('/stream', id='dj_harbor', port=HARBOR_PORT, auth=dj_auth, on_connect=dj_connect,
                 on_disconnect=dj_disconnect, buffer=BUFFER, max=MAX))

# Metadata insertion, used at connectino time above (hence the ref)
let (dj_harbor_insert_metadata, dj_harbor) = insert_metadata(dj_harbor)
dj_harbor_insert_metadata_ref := dj_harbor_insert_metadata
dj_harbor_insert_metadata(new_track=true, [])

# output.dummy() appears to be needed to avoid buffer overrun issues (ie the harbor always gets consumed)
ignore(output.dummy(id='dj_harbor_dummy', dj_harbor, fallible=true))

# Treat silence on the harbor as if a DJ weren't connected
dj_harbor = strip_blank(
    id='dj_harbor_strip',
    max_blank=MAX_SILENCE,
    start_blank=true,
    dj_harbor,
)

{% if settings.ZOOM_ENABLED %}
    zoom_metadata = ref 'Live Broadcast'
    server.register(
        usage='zoom_metadata [<json-str>]', description='Set metadata for Zoom broadcast (JSON string)', 'zoom_metadata', fun(data) -> begin
            if data != '' then
                zoom_metadata := of_json(default=!zoom_metadata, data)
            end
            'Metadata: #{!zoom_metadata}'
        end)
    zoom_enabled = interactive.bool('zoom_enabled', false)

    # Use a pulseaudio input for Zoom
    zoom = input.pulseaudio(id='zoom')
    ignore(output.dummy(id='zoom_dummy', zoom))

    zoom = switch(id='zoom_switch', track_sensitive=false, [(zoom_enabled, zoom)])

    # Treat silence on pulseaudio as if it weren't connected
    zoom = strip_blank(
        max_blank=MAX_SILENCE,
        id='zoom_strip',
        start_blank=true,
        min_noise=0.25,  # Higher threshold here since a microphone could be on but a room silent
        zoom,
    )
    zoom = map_metadata(update=false, strip=true, fun(_) -> begin
        [('title', !zoom_metadata)]
    end, zoom)
{% endif %}

# Pre-recorded broadcasts
prerecord = request.queue(id='prerecord')
prerecord = audio_to_stereo(id='prerecord_to_stereo', prerecord)

# Update status on track end
prerecord = on_end(id='prerecord_onend', delay=0., fun(_, _) -> begin
    # Clear status since timed_sources may be the only thing that changed
    last_status_without_timed_sources := reset_status
end, prerecord)
add_skip_command_carb(prerecord)

{% if config.AUTODJ_ENABLED %}
    # Auto DJ
    autodj = request.dynamic.list(
        # TODO: conservative always keeps one request in the queue, useful for skipping but
        # means station ID + could come several minutes afterwards. I think this isn't needed
        # but if we observe transitions to fallback from autoDJ unexpected this may need to be re-enabled
        id='autodj', conservative=false, length=REQUEST_QUEUE_LENGTH,
        retry_delay=REQUEST_RETRY_DELAY, timeout=REQUEST_TIMEOUT, fun() -> begin
            url = '#{API_PREFIX}next-track/'
            let ((_, status_code, _), _, response) = http.get(url, headers=API_HEADERS)
            if status_code == 200 then
                if list.assoc(default=false, 'has_asset', of_json(default=[('_', false)], response)) then
                    asset_uri = list.assoc(default='', 'asset_uri', of_json(default=[('_', '')], response))
                    log('autodj: selected URI #{asset_uri}')
                    [request.create(asset_uri)]
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
        # Clear status since timed_sources may be the only thing that changed
        last_status_without_timed_sources := reset_status
    end, autodj)

    # Having autodj safe for a few seconds means resolution loading files won't
    # transition to failsafe and just have a few seconds of silence
    add_skip_command_carb(autodj)
{% endif %}

# Our failsafe audio, right now some silly hold music.
failsafe = single(id='failsafe',
{% if config.HARBOR_FAILSAFE_AUDIO_FILE %}
    {{ settings.MEDIA_ROOT|add:'/'|add:config.HARBOR_FAILSAFE_AUDIO_FILE|liqval }}
{% else %}
    '/assets/hold-music.mp3'
{% endif %}
)

# If you add a source that has timed tracks, they should be added to this list
# in your user defined code below
timed_sources = [prerecord{% if config.AUTODJ_ENABLED %}, autodj{% endif %}]

#
# Our heirarchical sources. Items first in the list have higher precedence
# Format: (actual_source, 'Pretty Source Name')
#
# You can add to these using custom code, see below
#
source_hierarchy = [
    (prerecord, 'Prerecorded Broadcast'),
    (dj_harbor, 'Live DJ'),
    {% if not settings.ZOOM_ENABLED %}# Zoom disabled (ZOOM_ENABLED = 0 in .env file)
    # {% endif %}(zoom, 'Zoom Room'),
    {% if not config.AUTODJ_ENABLED %}# AutoDJ disabled (AUTODJ_ENABLED = False in configuration)
    # {% endif %}(autodj, 'AutoDJ'),
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

# Server status stuff, a bit messy but it puts together mixed-type JSON
current_metadata = ref []

def status_tuple()
    # List of sources
    active_sources = list.filter(fun(src) -> source.is_ready(fst(src)), source_hierarchy)
    streaming_source_id = list.hd(default='unknown', list.map(fun(src) -> source.id(fst(src)), active_sources))
    sources = '[' ^ string.concat(separator=',', list.mapi(fun(n, src) -> begin
        let (source, name) = src
        id = source.id(source)
        json_of_mixed_types(
            strs=[('id', id), ('name', name)], ints=[('precedence', n + 1)],
            bools=[('is_active', source.is_ready(source)), ('is_current_stream', id == streaming_source_id)])
    end, source_hierarchy)) ^ ']'

    # Live DJ
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
    timed_sources = list.map(fun(s) -> begin
        remaining = source.remaining(s)
        track_end_time = if remaining > 0. and not is_infinity(remaining) then now + remaining else -1. end
        (source.id(s), track_end_time)
    end, timed_sources)
    timed_sources = json_of(compact=true, list.filter(fun(s) -> snd(s) > -1., timed_sources))

    skippable_sources = json_of(compact=true, !skippable_sources)
    dj_harbor_source = json_of(compact=true, source.id(dj_harbor))
    metadata = json_of(compact=true, !current_metadata)
    server_info = json_of(compact=true, [('start_time', start_time)])

    # timed_source constantly changes, so don't include it in comparison looking for changes in update status timeout
    (sources, dj_harbor_source, live_user, skippable_sources, metadata, server_info, timed_sources)
end

def status_json_from_tuple(tuple)
    let (sources, dj_harbor_source, live_user, skippable_sources, metadata, server_info, timed_sources) = tuple
    '{"sources":#{sources},"dj_harbor_source":#{dj_harbor_source},"live_user":#{live_user},'
        ^ '"skippable_sources":#{skippable_sources},"timed_sources":#{timed_sources},"metadata":#{metadata},'
        ^ '"server_info": #{server_info}}'
end

def status_json()
    status_json_from_tuple(status_tuple())
end

server.register(usage='status', description='Get status of sources in JSON', 'status', fun(_) -> status_json())
server.register(usage='status_pretty', description='Get status of sources in JSON (pretty-printed)', 'status_pretty',
                fun(_) -> get_process_output('echo #{safe_quote(status_json())} | jq -SM'))

# Push notifications of status (using the SSE service)
def post_to_sse(json)
    log('hitting SSE service with status JSON')
    let ((_, status_code, _), _, _) = http.post(SSE_MESSAGE_URL, data=json)
    if status_code != 204 then
        log.severe('ERROR: failed to update sse service, expected status code 204 (got #{status_code})')
    end
end

on_shutdown(fun() -> post_to_sse('null'))
post_to_sse('null')  # Empty to start

STATUS_UPDATE_CHECK_INTERVAL = .1  # Check for changes to push via SSE every 100ms
add_timeout(fast=false, STATUS_UPDATE_CHECK_INTERVAL, fun() -> begin
    current_status_tuple = status_tuple()
    let (a, b, c, d, e, f, _) = current_status_tuple
    status_without_timed_sources = (a, b, c, d, e, f)
    # See if there are any changes
    if status_without_timed_sources != !last_status_without_timed_sources then
        last_status_without_timed_sources := status_without_timed_sources
        post_to_sse(status_json_from_tuple(current_status_tuple))
    end
    .STATUS_UPDATE_CHECK_INTERVAL
end)
# Radio playout below

# Our transition function used for logging, playing the "swoosh", and fadeouts
{% if config.HARBOR_TRANSITION_WITH_SWOOSH %}
    swoosh = single(
    {% if config.HARBOR_SWOOSH_AUDIO_FILE %}
        {{ settings.MEDIA_ROOT|add:'/'|add:config.HARBOR_SWOOSH_AUDIO_FILE|liqval }}
    {% else %}
        '/assets/transition.mp3'
    {% endif %}
    )
{% endif %}
def transition(~source, one, two)
    last_source_name = !current_source_name
    current_source_name := list.assoc(default='Unknown', source.id(source), source_hierarchy_lookups)
    log('Transitioning to #{source.id(source)} [#{source.id(one)} -> #{source.id(two)}]')
    log_event(type=EVENT_SOURCE_TRANSITION, 'Transitioned from #{last_source_name} to #{!current_source_name}')

    {% if config.AUTODJ_ENABLED %}
        # Skip to new track when transitioning to AutoDJ
        two = if source.id(source) == source.id(autodj) and source.id(one) != source.id(failsafe) then
            source.skip(autodj)
            # Avoid metadata duplication + any jitters from skipped track by sequencing after 50ms
            sequence([blank(duration=0.05), two])
        else
            two
        end
    {% endif %}

    {% if not config.HARBOR_TRANSITION_SECONDS and not config.HARBOR_TRANSITION_WITH_SWOOSH %}
        # No transition required
        two
    {% else %}
        add(normalize=false, [
            two,  # Second source first, since we wants its metadata (from add() in liquidsoap manual)
            {% if config.HARBOR_TRANSITION_WITH_SWOOSH %}
                once(swoosh),
            {% endif %}
            {% if config.HARBOR_TRANSITION_SECONDS %}
                fade.final(duration=TRANSITION_SECONDS, one),
            {% endif %}
        ])
    {% endif %}
end

# Our actual radio is a fallback based on source_hierarchy's precedence
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

# Metadata change function, used for SSE pushes and logging
radio = on_metadata(fun(m) -> begin
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
    # Borrowed from AzuraCast. Thanks!
    radio = normalize(target=0., window=0.03, gain_min=-16., gain_max=0., compress.exponential(radio, mu=1.))
{% endif %}

# Our raw WAVE format output harbor that upstream scripts connect to
output.harbor(
    %wav(duration=0., stereo=true, channels=2, samplesize=16, header=true),
    id='broadcast',
    mount='live',
    port=4000,
    radio,
)
