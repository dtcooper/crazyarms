%include "common.liq"

def ls_dir(path)
    get_process_lines('find #{string.escape(path)} -type f')
end

NOTIFICATIONS_ENABLED = conf_bool('NOTIFICATIONS_ENABLED')
NOTIFICATIONS_TO_EMAIL_ADDRS = of_json(default=[], conf(allow_empty=true, 'NOTIFICATIONS_TO_EMAIL_ADDRS'))
NOTIFICATIONS_FROM_EMAIL_ADDR = conf('NOTIFICATIONS_FROM_EMAIL_ADDR')
def notify(subject, body='')
    if NOTIFICATIONS_ENABLED and list.length(NOTIFICATIONS_TO_EMAIL_ADDRS) > 0 then
        to_addresses = string.concat(NOTIFICATIONS_TO_EMAIL_ADDRS, separator=', ')
        email = 'To: #{to_addresses}\r\nFrom: #{NOTIFICATIONS_FROM_EMAIL_ADDR}\r\nSubject: #{subject}\r\n\r\n#{body}'
        log('Sending notification to [#{to_addresses}]: #{subject}')
        ignore(run_process('echo #{quote(email)} | sendmail -t'))
    else
        log('Notification (email disabled): #{subject} // #{if body == "" then "[no body]" else body end}')
    end
end


set('server.telnet', conf_bool('TELNET_ENABLE'))
set('server.telnet.port', conf_int('TELNET_PORT'))
if file.exists('/.dockerenv') then
    # Docker only! Otherwise always localhost.
    set('server.telnet.bind_addr', '0.0.0.0')
end

notify('Harbor came online')

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

FAILSAFE_PATH = conf('FAILSAFE_PATH')
failsafe = single(id='failsafe', FAILSAFE_PATH)

AUTO_DJ_DIR = conf('AUTO_DJ_DIR')
AUTO_DJ_TRACKS_SUBDIR = conf('AUTO_DJ_TRACKS_SUBDIR')
AUTO_DJ_NUM_STOPSETS_PER_HOUR = conf_int('AUTO_DJ_NUM_STOPSETS_PER_HOUR')
AUTO_DJ_STOPSET_ROTATOR_SUBDIRS = of_json(default=[], conf(allow_empty=true, 'AUTO_DJ_STOPSET_ROTATOR_SUBDIRS'))
stopsets_enabled = list.length(AUTO_DJ_STOPSET_ROTATOR_SUBDIRS) > 0
if not stopsets_enabled then
    log('Stop sets disabled by configuration')
end

last_stopset_played = ref -1
current_stopset = ref []
tracks_list = ref []
autodj = request.dynamic(id='autodj', length=conf_float('REQUEST_QUEUE_LENGTH'), fun() -> begin
    current_datetime = int_of_string(string.trim(get_process_output("date '+%Y%m%d%H%M'")))
    current_minute = current_datetime mod 60
    interval_minute = current_minute mod (60 / AUTO_DJ_NUM_STOPSETS_PER_HOUR)
    current_interval = current_datetime - interval_minute

    # Generate a stopset if one isn't currently playing and the interval passes
    if stopsets_enabled and (list.length(!current_stopset) == 0)
            and (!last_stopset_played < current_interval) then
        log('autodj: last stopset played @ #{!last_stopset_played}. '
            ^ 'Interval #{current_interval} past due. Generating stopset')
        rotator_files = ref []
        # Get a mapping of [(path, files)] with files randomized
        list.iter(fun(path) -> begin
                if not list.mem_assoc(path, !rotator_files) then
                    rotator_files := list.add(
                        (path, list.randomize(ls_dir('#{AUTO_DJ_DIR}/#{path}'))),
                        !rotator_files,
                    )
                end
            end,
            AUTO_DJ_STOPSET_ROTATOR_SUBDIRS,
        )

        stopset = list.map(fun(path) -> begin
                # Get random list of files for this path
                files = list.assoc(default=[], path, !rotator_files)
                # Pick first one and remove from list
                file = list.hd(default=FAILSAFE_PATH, files)
                files = list.tl(files)
                # Add list with file removed back to rotator_files
                rotator_files := list.remove_assoc(path, !rotator_files)
                rotator_files := list.add((path, files), !rotator_files)
                file
            end,
            AUTO_DJ_STOPSET_ROTATOR_SUBDIRS,
        )
        log('autodj: stopset generated: #{string_of(stopset)}')
        current_stopset := stopset
    end

    request.create(
        if list.length(!current_stopset) > 0 then
            # Play through current stopset
            path = list.hd(default=FAILSAFE_PATH, !current_stopset)
            current_stopset := list.tl(!current_stopset)
            num_left = list.length(!current_stopset)
            if num_left == 0 then
                # When its on its last track, log played time.
                # (Probably should log it after this track, but who cares)
                last_stopset_played := current_datetime
            end
            log('autodj: playing "#{path}" from stopset. #{num_left} assets left in current stopset.')
            path
        else
            # Otherwise play tracks
            tracks = ls_dir('#{AUTO_DJ_DIR}/#{AUTO_DJ_TRACKS_SUBDIR}')
            path = if list.length(tracks) == 0 then
                FAILSAFE_PATH
            else
                if list.length(!tracks_list) == 0 then
                    tracks_list := list.randomize(tracks)
                end

                path = list.hd(default=FAILSAFE_PATH, !tracks_list)
                tracks_list := list.tl(!tracks_list)

                # If we've played through half the tracks, shuffle new list (don't include picked track)
                if list.length(!tracks_list) <  (list.length(tracks) / 2) then
                    tracks_list := list.remove(path, list.randomize(tracks))
                end

                path
            end
            log('autodj: playing track "#{path}"')
            path
        end
    )
end)
autodj = audio_to_stereo(id='autodj_to_stereo', autodj)


CROSSFADE_TIMER = conf_float('CROSSFADE_TIMER')
current_stream = ref source.id(failsafe)  # assume lowest precedence in fallback
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

radio_fallback_precedence = [dj_harbor, pulse_in, autodj, failsafe]
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

connections = ref []
INTERNAL_HARBOR_PASSWORD = conf('INTERNAL_HARBOR_PASSWORD')
output.harbor(
    %wav(duration=0., stereo=true, channels=2, samplesize=16, header=true),
    id='broadcast',
    mount='broadcast',
    port=conf_int('INTERNAL_HARBOR_PORT'),
    auth=fun(user, pass) -> pass == INTERNAL_HARBOR_PASSWORD,
    on_connect=fun(~headers, ~uri, ~protocol, ip) -> begin
        args = snd(url.split(uri))
        upstream = args["upstream"]
        connections := list.add((ip, upstream), !connections)
        log('Upstream "#{upstream}" connected')
    end,
    on_disconnect=fun(ip) -> begin
        conns = !connections
        upstream = conns[ip]
        connections := list.remove_assoc(ip, !connections)
        log('Upstream "#{upstream}" disconnected')
    end,
    radio
)
