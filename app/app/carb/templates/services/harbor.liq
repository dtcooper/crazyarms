set('server.telnet', true)
set('server.telnet.port', 1234)
set('server.telnet.bind_addr', '0.0.0.0')
set('server.timeout', -1.)

%include "harbor.vars.liq"

API_HEADERS = [('X-CARB-Secret-Key', SECRET_KEY)]
API_PREFIX = 'http://app:8000/harbor/'

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

failsafe = single('/hold-music.mp3')
radio = fallback(replay_metadata=false, track_sensitive=false, [request.equeue(id='request'), dj_harbor, failsafe])

output.harbor(
    %wav(duration=0., stereo=true, channels=2, samplesize=16, header=true),
    id='broadcast',
    mount='stream',
    port=2817,
    radio,
)
