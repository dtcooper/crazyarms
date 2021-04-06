import base64

from jinja2 import Environment


def liqval(value, comment_string=True):
    if isinstance(value, bool):
        encoded = str(value).lower()

    elif isinstance(value, float):
        encoded = f"{value:.5g}"  # 5 decimal places
        if "." not in encoded:
            encoded += "."

    elif isinstance(value, int):
        encoded = value

    else:
        if not isinstance(value, str):
            value = str(value)

        # Best way to encode a string, since it's not exactly documented escape
        # characters properly for liquidsoap.
        encoded = base64.b64encode(value.encode("utf-8")).decode("utf-8")
        encoded = f'base64.decode("{encoded}")'
        if comment_string:
            encoded += f"  # {value!r}"

    return encoded


def environment(**options):
    env = Environment(**options)
    env.filters.update({
        'liqval': liqval,
        'tobool': lambda v: bool(v),
    })
    return env
