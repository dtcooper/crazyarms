{% autoescape off %}

set('server.telnet', true)
set('server.telnet.port', 1234)
set('server.telnet.bind_addr', '0.0.0.0')
set('server.timeout', -1.)

API_HEADERS = [('X-CARB-Secret-Key', '{{ settings.SECRET_KEY }}')]
API_PREFIX = 'http://admin:8000/harbor/'

def dj_auth(username, password)
    data = json_of([('username', username), ('password', password)])
    let ((_, status_code, _), _, response) = http.post('#{API_PREFIX}auth/', headers=API_HEADERS, data=data)
    if status_code != 200 then
        false
    else
        response = of_json(default=[('allowed', false)], response)
        list.assoc(default=false, 'allowed', response)
    end
end

dj_harbor = audio_to_stereo(
    input.harbor(
        '/stream',
        id='dj_harbor',
        port=8001,
        auth=dj_auth,
        buffer=5.,
        max=10.,
    ),
)
ignore(output.dummy(dj_harbor, fallible=true))

failsafe = single('/failsafe.mp3')
radio = fallback(replay_metadata=false, track_sensitive=false, [dj_harbor, failsafe])

{% if settings.ICECAST_ENABLED %}
output.icecast(
  %mp3(bitrate=128),
  mount="/live",
  host="icecast",
  port=8000,
  password="{{ config.ICECAST_SOURCE_PASSWORD }}",
  fallible=true,
  radio,
)
{% endif %}

{% if not settings.ICECAST_ENABLED or UPSTREAM_SERVERS %}
output.dummy(radio, fallible=true)
{% endif %}

{% endautoescape %}
