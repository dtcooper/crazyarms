{% load carb %}

{% for name, val in vars.items %}
{{ name }} = {{ val|liqval }}
{% endfor %}
