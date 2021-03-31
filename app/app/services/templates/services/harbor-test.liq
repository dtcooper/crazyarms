{% load services %}

SCRIPT_NAME = 'Test Harbor'
HEALTHCHECK_PORT = 8002
%include "library.liq"

set('server.telnet', true)
set('server.telnet.port', 1235)

HARBOR_PORT = 8002
MASTER_PASSWORD = {{ config.HARBOR_TEST_MASTER_PASSWORD|liqval }}

{% if config.HARBOR_TRANSITION_SECONDS %}
    TRANSITION_SECONDS = {{ config.HARBOR_TRANSITION_SECONDS|liqval }}
{% endif %}
{% if config.HARBOR_TRANSITION_WITH_SWOOSH %}
    swoosh = single(
    {% if config.HARBOR_SWOOSH_AUDIO_FILE %}
        {{ settings.MEDIA_ROOT|add:'/'|add:config.HARBOR_SWOOSH_AUDIO_FILE|liqval }}
    {% else %}
        '/assets/transition.mp3'
    {% endif %}
    )
{% endif %}

{% if config.HARBOR_TRANSITION_SECONDS or config.HARBOR_TRANSITION_WITH_SWOOSH %}
    def transition(one, two)
        add(normalize=false, [
            two,  # Second source first, since we wants its metadata (from add() in liquidsoap manual)
            {% if config.HARBOR_TRANSITION_WITH_SWOOSH %}
                once(swoosh),
            {% endif %}
            {% if config.HARBOR_TRANSITION_SECONDS %}
                fade.final(duration=TRANSITION_SECONDS, one),
            {% endif %}
        ])
    end
{% endif %}

def dj_auth(username, password)
    if password == MASTER_PASSWORD then
        true
    else
        data = json_of(compact=true, [('username', username), ('password', password)])
        url = '#{API_PREFIX}dj-auth/'
        let ((_, status_code, _), _, response) = http.post(url, headers=API_HEADERS, data=data)
        if status_code == 200 then
            authorized = list.assoc(default=false, 'authorized', of_json(default=[('_', false)], response))
            log('dj_auth: authorize with API for user #{username} returned: #{string_of(authorized)}')
            authorized
        else
            log('ERROR: dj_auth: got non-200 status got API (#{status_code}) for user #{username}')
            false
        end
    end
end

dj_harbor = audio_to_stereo(
    id='dj_harbor_to_stereo',
    input.harbor(
        '/stream',
        id='dj_harbor',
        port=HARBOR_PORT,
        auth=dj_auth,
        buffer=BUFFER,
        max=MAX),
    )

failsafe = audio_to_stereo(id='failsafe_stereo', single(id='failsafe',
{% if config.HARBOR_FAILSAFE_AUDIO_FILE %}
    {{ settings.MEDIA_ROOT|add:'/'|add:config.HARBOR_FAILSAFE_AUDIO_FILE|liqval }}
{% else %}
    '/assets/hold-music.mp3'
{% endif %}
))

radio = fallback(
    id='radio',
    replay_metadata=false,
    track_sensitive=false,
    {% if config.HARBOR_TRANSITION_SECONDS or config.HARBOR_TRANSITION_WITH_SWOOSH %}
        transitions=[transition, transition],
    {% endif %}
    [dj_harbor, failsafe],
  )

output.harbor(
    %wav(duration=0., stereo=true, channels=2, samplesize=16, header=true),
    id='broadcast',
    mount='internal',
    port=4001,
    radio,
)
