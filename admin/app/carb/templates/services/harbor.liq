{% autoescape off %}

set('server.telnet', true)
set('server.telnet.port', 1234)
set('server.telnet.bind_addr', '0.0.0.0')
set('server.timeout', -1.)

# Sample input, WFMU
input = input.http('http://stream0.wfmu.org/freeform-128k.mp3')

output.icecast(
  %mp3(bitrate=128),
  mount="/live",
  host="icecast",
  port=8000,
  password="{{ config.ICECAST_SOURCE_PASSWORD }}",
  fallible=true,
  input,
)

{% endautoescape %}
