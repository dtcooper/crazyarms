{% load carb %}

{% for name, val in vars.items %}
{{ name }} = {{ val|liquidsoap_value }}
{% endfor %}
