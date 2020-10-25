import base64

from django import template


register = template.Library()


@register.filter
def liquidsoap_value(value):
    if isinstance(value, str):
        encoded = base64.b64encode(value.encode('utf-8')).decode('utf-8')
        encoded = f'base64.decode("{encoded}")  # {value!r}'
    elif isinstance(value, bool):
        encoded = str(value).lower()
    elif isinstance(value, float):
        encoded = str(value)
        if '.' not in encoded:
            encoded += '.'
    elif isinstance(value, int):
        encoded = value
    else:
        raise ValueError('Invalid value to encode for liquidsoap')
    return encoded
