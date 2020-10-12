import base64

from django import template


register = template.Library()


@register.filter
def boolstr(value):
    return 'true' if value else 'false'


@register.filter
def liqstr(value, with_comment=False):
    encoded = base64.b64encode(value.encode("utf-8")).decode("utf-8")
    encoded = f'base64.decode("{encoded}")'
    if with_comment:
        encoded = f'{encoded}  # {value!r}'
    return encoded
