%include "common.liq"

def ls_dir(path)
    get_process_lines('find -L #{string.escape(path)} -type f')
end

def pretty_seconds(seconds)
    seconds = if seconds < 0. then 0. else seconds end
    string.trim(get_process_output(
        'python3 -c "import datetime as d; print(d.timedelta(seconds=#{string_of(int_of_float(seconds))}))"'))
end

def sanitize_password(password)
    string.trim(string.case(lower=true, password))
end


shutting_down = ref false  # Avoid wacky shutdown notifications
on_shutdown(fun() -> shutting_down := true)

NOTIFICATIONS_ENABLED = conf.bool('NOTIFICATIONS_ENABLED')
NOTIFICATIONS_TO_EMAIL_ADDRS = conf.list(allow_empty=not NOTIFICATIONS_ENABLED, 'NOTIFICATIONS_TO_EMAIL_ADDRS')
NOTIFICATIONS_FROM_EMAIL_ADDR = conf(allow_empty=not NOTIFICATIONS_ENABLED, 'NOTIFICATIONS_FROM_EMAIL_ADDR')
SMS_NOTIFICATIONS_ENABLED = conf.bool('SMS_NOTIFICATIONS_ENABLED')
SMS_FROM_NUMBER = conf(allow_empty=not SMS_NOTIFICATIONS_ENABLED, 'SMS_FROM_NUMBER')
SMS_TO_NUMBERS = conf.list(allow_empty=not SMS_NOTIFICATIONS_ENABLED, 'SMS_TO_NUMBERS')
SMS_TWILIO_ACCOUNT_SID = conf(allow_empty=not SMS_NOTIFICATIONS_ENABLED, 'SMS_TWILIO_ACCOUNT_SID')
SMS_TWILIO_AUTH_TOKEN = conf(allow_empty=not SMS_NOTIFICATIONS_ENABLED, 'SMS_TWILIO_AUTH_TOKEN')
def notify(subject, body='')
    if not !shutting_down and NOTIFICATIONS_ENABLED then
        to_addresses = string.concat(NOTIFICATIONS_TO_EMAIL_ADDRS, separator=', ')
        date = string.trim(get_process_output('date'))
        email = 'To: #{to_addresses}\r\nFrom: #{NOTIFICATIONS_FROM_EMAIL_ADDR}\r\nSubject: #{date} #{subject}\r\n\r\n#{body}'
        log('Sending notification to [#{to_addresses}]: #{subject}')
        add_timeout(0., fun() -> begin
            ignore(run_process(timeout=2., 'echo #{string.escape(email)} | sendmail -t'))
            -1.
        end)
    else
        log('Notification (email disabled): #{subject} // #{if body == "" then "[no body]" else body end}')
    end

    if not !shutting_down and SMS_NOTIFICATIONS_ENABLED then
        add_timeout(0., fun() -> begin
            ignore(list.map(fun(number) -> begin
                log('Sending SMS notification to #{number}: #{subject}')
                run_process(timeout=10.,
                    'curl -s -X POST -d "Body="#{string.escape(subject)} '
                    ^ '-d "From="#{string.escape(SMS_FROM_NUMBER)} '
                    ^ '-d "To="#{string.escape(number)} '
                    ^ '-u #{string.escape(SMS_TWILIO_ACCOUNT_SID)}":"#{string.escape(SMS_TWILIO_AUTH_TOKEN)} '
                    ^ '"https://api.twilio.com/2010-04-01/Accounts/"#{string.escape(SMS_TWILIO_ACCOUNT_SID)}"/Messages"')
            end, SMS_TO_NUMBERS))
            -1.
        end)
    end
end


set('server.telnet', conf.bool('TELNET_ENABLE'))
set('server.telnet.port', conf.int('TELNET_PORT'))

DJ_MASTER_PASSWORDS = conf.list('DJ_MASTER_PASSWORDS')

### Priority DJ mount (only accepts master password) ###
dj_priority_login_time = ref -1.
dj_priority_harbor = input.harbor(
    conf('DJ_PRIORITY_MOUNT_NAME'),
    id='dj_priority_harbor',
    port=conf.int('DJ_PORT'),
    max=conf.float('INPUT_MAX'),
    buffer=conf.float('INPUT_BUFFER'),
    auth=fun(user, pass) -> begin
        if list.mem(pass, DJ_MASTER_PASSWORDS) then
            log('Accepted master DJ password (priority mount)')
            true
        else
            log('Rejected password "#{pass}" (priority mount)')
            false
        end
    end,
    on_connect=fun(headers) -> begin
        ip_address = list.hd(default='source client ip unknown', server.execute('dj_priority_harbor.status'))
        dj_priority_login_time := time()
        log_line = 'Master DJ connected (priority mount)'
        log(log_line)
        notify(log_line, 'master (priority mount)\n#{ip_address}\n\n#{json_of(headers)}')
    end,
    on_disconnect=fun() -> begin
        if !dj_priority_login_time >= 0. then
            total_time = pretty_seconds(time() - !dj_priority_login_time)
            log_line = 'Master DJ (priority mount) disconnected after #{total_time}'
            dj_priority_login_time := -1.
            log(log_line)
            notify(log_line)
        end
    end
)
output.dummy(dj_priority_harbor, id='dj_priority_harbor_dummy', fallible=true)

dj_priority_id = 'dj_priority_harbor_strip'
dj_priority_harbor = strip_blank(
    max_blank=conf.float('DJ_MAX_SILENCE'),
    id=dj_priority_id,
    start_blank=true,
    audio_to_stereo(id='dj_priority_harbor_audio_to_stereo', dj_priority_harbor),
)

### DJ mount ###
DJ_AUTH_ENABLED = conf.bool('DJ_AUTH_ENABLED')
DJ_AUTH_SHEET_KEY = if DJ_AUTH_ENABLED then conf('DJ_AUTH_SHEET_KEY') else '' end
DJ_AUTH_GRACE_PERIOD = if DJ_AUTH_ENABLED then conf.int('DJ_AUTH_GRACE_PERIOD') else 0 end
DJ_AUTH_ENFORCE_SCHEDULE = conf.bool('DJ_AUTH_ENFORCE_SCHEDULE')
auth_cmd = './auth.py -k #{string.escape(DJ_AUTH_SHEET_KEY)} -g #{string_of(DJ_AUTH_GRACE_PERIOD)}'

if DJ_AUTH_ENABLED then
    log('Authentication enabled.')
    add_timeout(1., fun() -> begin
        if test_process(timeout=15., auth_cmd) then
            log("User data sync'd")
        else
            log("Error sync'ing user data")
        end
        30.
    end)
end

dj_raw_data = ref 'disconnected'
dj_name = ref 'N/A'
dj_password = ref ''
dj_login_time = ref -1.
dj_kickoff_time = ref -1.
dj_just_booted = ref false
dj_ban_list = ref []
dj_harbor = input.harbor(
    conf('DJ_MOUNT_NAME'),
    id='dj_harbor',
    port=conf.int('DJ_PORT'),
    max=conf.float('INPUT_MAX'),
    buffer=conf.float('INPUT_BUFFER'),
    auth=fun(user, pass) -> begin
        if list.mem(pass, DJ_MASTER_PASSWORDS) then
            log('Accepted master DJ password')
            dj_raw_data := 'master'
            true
        elsif DJ_AUTH_ENABLED then
            is_banned = ref false
            list.iter(fun(ban) -> begin
                ban_pass = fst(ban)
                until = snd(ban)
                now = time()
                if sanitize_password(pass) == ban_pass and (until < 0. or now < until) then
                    is_banned := true
                    log('Password "#{pass}" currently on ban list for'
                        ^ if until < 0.0 then 'ever' else ' another #{string_of(int_of_float(until - now))}s' end)
                end
                if until >= 0. and now >= until then
                    log('purged password "#{ban_pass}" from ban list')
                    dj_ban_list := list.remove_assoc(ban_pass, !dj_ban_list)
                end
            end, !dj_ban_list)

            if !is_banned then
                false
            else
                cmd_output = get_process_output('#{auth_cmd} #{pass}')
                dj_raw_data := cmd_output
                data = of_json(default=[], cmd_output)
                bool_data = of_json(default=[], cmd_output)

                if list.assoc(default=false, 'valid_user', bool_data) then
                    if DJ_AUTH_ENFORCE_SCHEDULE then
                        allow = list.assoc(default=false, 'currently_authorized', bool_data)
                        log('#{if allow then "Accepted" else "Rejected" end} password for DJ "#{data["name"]}", '
                            ^ 'authorized for window #{data["start"]} to #{data["end"]}')
                        allow
                    else
                        log('Accepted password for DJ "#{data["name"]}" (schedule unenforced by config)')
                        true
                    end
                else
                    log('Rejected password "#{pass}"')
                    false
                end
            end
        else
            log('Rejected password "#{pass}" (DJ auth disabled)')
            false
        end
    end,
    on_connect=fun(headers) -> begin
        ip_address = list.hd(default='source client ip unknown', server.execute('dj_harbor.status'))
        data = of_json(default=[], !dj_raw_data)
        if DJ_AUTH_ENFORCE_SCHEDULE then
            dj_kickoff_time := float_of_string(list.assoc(default='-1', 'end_with_grace_period_unix', data))
        end

        dj_login_time := time()
        dj_name := list.assoc(default='Master DJ', 'name', data)
        dj_password := data['password_sanitized']
        log('#{!dj_name} connected')
        notify('#{!dj_name} connected', '#{!dj_name} connected\n#{ip_address}\n\n#{json_of(headers)}')
    end,
    on_disconnect=fun() -> begin
        dj_kickoff_time := -1.
        if !dj_raw_data != 'disconnected' then
            total_time = pretty_seconds(time() - !dj_login_time)
            log_line = '#{!dj_name} disconnected after #{total_time}'
                       ^ if !dj_just_booted then ' (kicked off)' else '' end
            dj_just_booted := false
            dj_raw_data := 'disconnected'
            dj_name := 'N/A'
            dj_password := ''
            log(log_line)
            notify(log_line)
        end
    end
)
output.dummy(dj_harbor, id='dj_harbor_dummy', fallible=true)

if DJ_AUTH_ENFORCE_SCHEDULE then
    log('Installing DJ kickoff timer')
    add_timeout(1., fun() -> begin
        # 1 second to make sure harbor doesn't reauthenticate
        if !dj_kickoff_time >= 0.0 and (time() - 1.0) > !dj_kickoff_time then
            dj_kickoff_time := -1.
            dj_just_booted := true
            log('Booting DJ due to running after kickoff time')
            ignore(server.execute('dj_harbor.stop'))
        end
        5.
    end)
end

dj_id = 'dj_harbor_strip'
dj_harbor = strip_blank(
    max_blank=conf.float('DJ_MAX_SILENCE'),
    id=dj_id,
    start_blank=true,
    audio_to_stereo(id='dj_harbor_audio_to_stereo', dj_harbor),
)


### Pulseaudio (Zoom) mount ###
PULSE_DEVICE = conf(allow_empty=true, 'PULSE_DEVICE')
log('Listen to pulse device: #{if PULSE_DEVICE == "" then "[default]" else PULSE_DEVICE end}')
pulse_in = input.pulseaudio(device=PULSE_DEVICE)
output.dummy(id='pulse_in', pulse_in)

PULSE_MAX_SILENCE = conf.float('PULSE_MAX_SILENCE')
pulse_in_id = 'pulse_in_strip'
pulse_in = strip_blank(
    max_blank=PULSE_MAX_SILENCE,
    id=pulse_in_id,
    start_blank=true,
    pulse_in,
)


### Failsafe mp3 (last resort) ###
FAILSAFE_PATH = conf('FAILSAFE_PATH')
failsafe_id = 'failsafe'
failsafe = single(id=failsafe_id, FAILSAFE_PATH)


## AutoDJ ###
AUTO_DJ_DIR = conf('AUTO_DJ_DIR')
AUTO_DJ_TRACKS_SUBDIR = conf('AUTO_DJ_TRACKS_SUBDIR')
AUTO_DJ_NUM_STOPSETS_PER_HOUR = conf.int('AUTO_DJ_NUM_STOPSETS_PER_HOUR')
AUTO_DJ_STOPSET_ROTATOR_SUBDIRS = conf.list(allow_empty=true, 'AUTO_DJ_STOPSET_ROTATOR_SUBDIRS')
stopsets_enabled = list.length(AUTO_DJ_STOPSET_ROTATOR_SUBDIRS) > 0
if not stopsets_enabled then
    log('Stop sets disabled by configuration')
end

last_stopset_played = ref -1
current_stopset = ref []
tracks_list = ref []
autodj = request.dynamic.list(id='autodj', length=conf.float('REQUEST_QUEUE_LENGTH'), fun() -> begin
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

    [request.create(
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
    )]
end)

autodj_id = 'autodj_to_stereo'
autodj = audio_to_stereo(id=autodj_id, autodj)


### Fallback radio ###
CROSSFADE_TIMER = conf.float('CROSSFADE_TIMER')
current_stream = ref source.id(failsafe)  # assume lowest precedence in fallback
def crossfade(~source, one, two)
    log('Transitioning to #{source.id(source)} [#{source.id(one)} -> #{source.id(two)}]')

    new_stream = source.id(source)
    if new_stream == source.id(pulse_in) then
        notify('Pulseaudio (Zoom) started streaming', 'Noise heard on pulseaudio input device')
    elsif !current_stream == source.id(pulse_in) and new_stream != source.id(pulse_in) then
        notify(
            'Pulseaudio (Zoom) stopped streaming',
            'Remote DJ logged in or #{string_of(PULSE_MAX_SILENCE)}s silence on pulseaudio input device',
        )
    end
    current_stream := new_stream

    add(normalize=false, [
        sequence([
            blank(duration=CROSSFADE_TIMER / 2.),
            fade.initial(duration=CROSSFADE_TIMER / 2., two)
        ]),
        fade.final(duration=CROSSFADE_TIMER, one)
    ])
end

radio_fallback_precedence = [dj_priority_harbor, dj_harbor, pulse_in, autodj, failsafe]
radio = fallback(
    id='radio',
    track_sensitive=false,
    transitions=list.map(fun(s) -> crossfade(source=s), radio_fallback_precedence),
    radio_fallback_precedence,
)

radio = if conf.bool('OUTPUT_COMPRESSOR_ENABLE') then
    log('Enabling output compressor')
    nrj(radio)
else
    radio
end


### Icecast output (wave format) ###
INTERNAL_HARBOR_PASSWORD = conf('INTERNAL_HARBOR_PASSWORD')
connections = ref []
output.harbor(
    %wav(duration=0., stereo=true, channels=2, samplesize=16, header=true),
    id='broadcast',
    mount='stream',
    port=conf.int('INTERNAL_HARBOR_PORT'),
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
    radio,
)

notify('Harbor came online', 'This does not necessarily mean listeners were disconnected')


### Status page
def protected(func)
    fun(~protocol, ~data, ~headers, uri) -> begin
        auth = headers['Authorization']
        allowed = if auth == '' then false else
            auth = string.extract(pattern='^Basic (.+)$', auth)
            if list.length(auth) > 0 then
                auth = string.extract(pattern='^[^:]*:(.*)', base64.decode(auth['1']))
                if list.length(auth) > 0 then
                    list.mem(auth["1"], DJ_MASTER_PASSWORDS)
                else
                    false
                end
            else
                false
            end
        end

        if allowed then
            func(protocol=protocol, data=data, headers=headers, uri)
        else
            auth_headers = [('WWW-Authenticate', 'Basic realm="Password Required", charset="UTF-8"')]
            http_response(protocol=protocol, code=401, headers=auth_headers, data='')
        end
    end
end

STREAMS_PRETTY = [(dj_priority_id, 'Remote DJ (priority)'), (dj_id, 'Remote DJ'),
                  (pulse_in_id, 'Pulseaudio (Zoom)'), (autodj_id, 'AutoDJ'), (failsafe_id, 'Failsafe')]
def status_json()
    data = [('stream', list.assoc(default='Unknown', !current_stream, STREAMS_PRETTY))]
    json_of(compact=true, list.append(data,
        if !current_stream == dj_priority_id then
            [('conn_timedelta', pretty_seconds(time() - !dj_priority_login_time)), ('dj_name', 'Master DJ'),
             ('kickoff_time', 'N/A')]
        elsif !current_stream == dj_id then
            [('conn_timedelta', pretty_seconds(time() - !dj_login_time)), ('dj_name', !dj_name),
             ('kickoff_time', if !dj_kickoff_time >= 0. then string_of(!dj_kickoff_time) else 'N/A' end)]
        else
            [('conn_timedelta', 'N/A'), ('dj_name', 'N/A'), ('kickoff_time', 'N/A')]
        end
    ))
end

HTML = file.contents('status.html')
harbor.http.register(
    port=conf.int('DJ_PORT'), method='GET', '^/status/?$',
    protected(fun(~protocol, ~data, ~headers, uri) -> begin
        # If we're daemonizing cache HTML file
        html = if daemonize then HTML else file.contents('status.html') end
        html = string.replace(pattern='__JSON_DATA__', fun(_) -> status_json(), html)
        http_response(protocol=protocol, code=200, headers=[('Content-Type', 'text/html')], data=html)
    end))

harbor.http.register(
    port=conf.int('DJ_PORT'), method='GET', '^/status/data\\.json$',
    protected(fun(~protocol, ~data, ~headers, uri) ->
        http_response(protocol=protocol, code=200, headers=[('Content-Type', 'application/json')],
                      data=status_json())))

harbor.http.register(
    port=conf.int('DJ_PORT'), method='POST', '^/status/password\\.text$',
    protected(fun(~protocol, ~data, ~headers, uri) -> begin
        text = if list.mem(data, DJ_MASTER_PASSWORDS) then
            'Master DJ Password. Always authorized.'
        else
            get_process_output('#{auth_cmd} -f #{string.escape(data)}')
        end

        http_response(protocol=protocol, code=200, headers=[('Content-Type', 'text/plain')], data=text)
    end))

harbor.http.register(
    port=conf.int('DJ_PORT'), method='POST', '^/status/kick\\.text$',
    protected(fun(~protocol, ~data, ~headers, uri) -> begin
        kicked_dj = if !dj_kickoff_time >= 0.0 and !dj_password != '' then
            kicked_dj = !dj_name
            if data == 'forever' then
                dj_ban_list := list.add((!dj_password, -1.), !dj_ban_list)
            elsif int_of_string(data) > 0 then
                dj_ban_list := list.add((!dj_password, time() + float_of_string(data)), !dj_ban_list)
            end
            dj_kickoff_time := -1.
            dj_just_booted := true
            log('Booting DJ from UI (#{data} seconds)')
            ignore(server.execute('dj_harbor.stop'))
            kicked_dj
        else
            'No DJ currently eligible to be'
        end

        http_response(protocol=protocol, code=200, headers=[('Content-Type', 'text/plain')], data='DJ #{kicked_dj} booted')
    end))
