import sys
from unittest.mock import Mock

_django_settings = None


def get_django_settings():
    global _django_settings
    if _django_settings is None:
        sys.path.append("app/app")
        # Mock out imports
        sys.modules.update(
            {
                "django.utils.safestring": Mock(mark_safe=lambda s: s),
                "environ": Mock(Env=lambda: Mock(bool=lambda *args, **kwargs: True)),
            }
        )
        from crazyarms import settings

        _django_settings = settings
    return _django_settings


def get_constance_config_type(default, type_hint=None):
    types_to_string = {
        int: "Integer",
        float: "Decimal",
        bool: "Boolean (true or false)",
        str: "String",
    }
    type_hints_to_string = {
        "clearable_file": "File",
        "email": "Email Address",
        "nonzero_positive_int": "Integer (non-zero)",
        "positive_float": "Decimal (non-negative)",
        "positive_int": "Integer (non-negative)",
        "required_char": "String (required)",
        "zoom_minutes": "Integer (number of minutes)",
    }

    settings = get_django_settings()
    for choice_field in (
        "asset_bitrate_choices",
        "asset_encoding_choices",
        "autodj_requests_choices",
    ):
        choices = settings.CONSTANCE_ADDITIONAL_FIELDS[choice_field][1]["choices"]
        type_hints_to_string[
            choice_field
        ] = f'Choice of: {", ".join(choice for _, choice in choices)}'

    if type_hint is None or type_hint not in type_hints_to_string:
        return types_to_string[type(default)]
    else:
        return type_hints_to_string[type_hint]


def define_env(env):
    env.variables["DJANGO_SETTINGS"] = get_django_settings()
    with open("LICENSE", "r") as license:
        env.variables["LICENSE"] = license.read()
    with open(".default.env", "r") as default_env:
        env.variables["DEFAULT_ENV"] = default_env.read()
    env.macro(get_constance_config_type)
