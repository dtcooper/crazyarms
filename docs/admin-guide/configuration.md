# Configuration

There are three major ways to configure Crazy Arms,

1. [Station Settings in the station admin site](#station-settings-dynamic-settings)
2. [The startup environment file (`.env`)](#the-environment-file-env-static-settings)
3. [The Harbor source code, using Liquidsoap](#liquidsoap-source-advanced)

## Station Settings (Dynamic Settings)

In the station admin site, the following configuration options are available, and are
_dynamically configured,_ which is to say they can be changed at any time without
having to restart (and rebuild) the Crazy Arms server. Anyone with administrator
privileges can edit these in the web app.

!!! warning "Some Settings May Not Be Available"
    If Zoom or local Icecast server is disabled in the `.env` file, those
    sections will not be available. See
    [more information on the `.env` file below](#the-environment-file-env-static-settings).

Below are a list of configuration options, organized by section.

{% for section, config_names in DJANGO_SETTINGS.CONSTANCE_CONFIG_FIELDSETS.items() %}
### {{ section }}

!!! info ""
    {% for name in config_names %}
    {% with config=DJANGO_SETTINGS.CONSTANCE_CONFIG[name] %}
    {% with default=config[0], description=config[1], type=config[2] %}
    `{{ name }}` --- **Type: {{ get_constance_config_type(default, type) }}**
    :   {{ description }}
    {% endwith %}
    {% endwith %}
    {% endfor %}
{% endfor %}

## The Environment File -- `.env` (Static Settings)

When Crazy Arms starts for the first time with `./compose.sh`, you'll get asked
a series of simple questions. In your root directory, all that's happening is
the file `.default.env` is being modified and copied to `.env`.

!!! danger "Advanced Users Only"
    Editing the `.env` file is meant to be done once at installation (or rarely),
    and is intended for _systems administrators_ only, ie the nerds who set up
    Crazy Arms for your station. If your just a regular admin user, you'll
    probably be more interested in the [station settings](#station-settings-dynamic-settings)
    above.

!!! warning "Which Services Start"
    If you edit `ZOOM_ENABLED`, `ICECAST_ENABLED`, `EMAIL_ENABLED`,
    `HARBOR_TELNET_WEB_ENABLED`, `RTMP_ENABLED` you actually are controlling
    which services (or Docker containers) Crazy Arms starts up. This is the
    reason why these settings are _static,_ since the list of containers
    we choose to run is determined at start time.

Below is a copy of the `.default.env` file that shipped with Crazy Arms which
does a decent enough job of explaining what each option does.

```
{{ DEFAULT_ENV }}
```


## Liquidsoap Source (Advanced)


TODO

* [Liquidsoap](https://www.liquidsoap.info/)
* It's complicated but lots of fun to use.
