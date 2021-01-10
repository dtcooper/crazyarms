# Technical TODOs

## Pre-launch

- [ ] Documentation - _underway using mkdocs_
    - [x] Initial setup
    - [x] env file
    - [ ] docker build process + describing `./compose.sh` + `overrides.yml`
    - [ ] Add streaming instructions page for users
    - [ ] AutoDJ weighting concept
    - [x] Harbor architecture and concepts
- [x] AutoDJ
    - [x] Playlists
    - [x] Ad rotators + stopsets
    - [x] Weighting similar to [Tomato](https://github.com/dtcooper/tomato) (playlists are weighted,
      which should be enough)
    - [x] [select2](https://django-easy-select2.readthedocs.io/) requests in webui (add a new list in
        redis that gets popped from?)
- [x] Finish Zoom broadcasting
    - [x] needs a second pass, and a better show length picker that limits users time based on google calendar
    - [x] time remaining of current Zoom Show
    - [x] Indicator about why the zoom form doesn't show for calendar based auth
    - [ ] deal with invalid meeting popup
- [ ] Code cleanup
    - [ ] Clean up Dockerfiles stripping dev stuff
    - [ ] Go over `TODO`s and `XXX`s in codebase
    - [ ] Pin versions in all Dockerfiles, and Python packages (using [Poetry](https://python-poetry.org/))
- [x] Unit tests for at least the Django app - _skeleton done_
    - [ ] major second pass, fix broken tests, aim for high coverage _(or 100%)_
- [x] Mature `strip_blank` implementation
- [x] Convert some Django views to class-based
    - [x] `api` package
    - [x] `webui` package
- [x] Player for local icecast on status page
- [x] Make track log a more generic playout log, with asset playing on metadata one
    particular type.
- [x] Convert logging to redis queue (so web server doesn't have to be up to log)
    (decided to use `psql` to directly insert into the DB)
- [x] Kick off DJs outside of calendar times (with a grace period)
- [x] Add make active/disable quick actions for playlists and stopsets
- [x] Add scheduled time inline to broadcasts asset creation
- [x] Hide skip track button for lower precedence sources
- [x] Copy change: rename "precedence" -> "priority"
- [x] BUG: Edit profile seems to have re-enabled harbor access type
- [x] Thoroughly test new ffprobe + ffmpeg flows for audio assets + task
- [x] Harbor: use an add_timeout poll to check for `status_json()` changes rather than
    hooks `update_status[_ref]()` hooks throughout the code.
- [x] GCal shows stored as `ManyToManyField`
    - [x] add show name to JSON, useful for Zoom or Liquidsoap metadata am I sure I want this??? :tongue:
- [ ] Tasks to purge failed broadcasts/assets + unstuck processing ones, clean sftpgo files
- [x] Re-try broadcasts for which underlying assets which aren't `READY` every 2 seconds.
    Fix asset's inline broadcasts.
- [x] Remove `sse` service and use nginx module [nchan](https://nchan.io/)
- [x] Add sftp service using sftpgo
    - [x] Deal with WinSCP's `.filepart` situation
    - [x] Add ability to use SSH authorized keys.
- [x] Rename uploads with valid contents but wrong extension (ie file that's an mp3 but named wav)
- [x] User emails
    - [x] Users can update their email address in their profile (`EMAIL_ENABLED` + verification only)
    - [x] We don't really need a postfix container. Just configure Django to send email directly.
    - [x] Create user flow that sends user an email (and possibly they fill out their details)
    - [x] Consistent "From: " emails
    - [x] Add account username to set password emails
- [x] rtmp streaming using nginx-rtmp
- [ ] huey logs seem to print twice / django logging seems overly verbose (maybe just in gunicorn?)
- [ ] use [multirun](https://github.com/nicolas-van/multirun) for nginx (nginx + certbot),
    and icecast (icecast + notify) containers
- [x] investigate whether asset models should use `clean()` or `full_clean()`?
    (Does it only matter with unique indexes?)
- [x] "There were errors on this page" message for forms with errors at top of page. Possible mixin
    that adds a message when `form_invalid(...)`
- [ ] ~~Don't organize assets by folder prefixes that say where they came from like `upload/`, `external/`, etc
    instead organize by `<artist-normalized-and-non-empty>/<album-normalized-and-non-empty>/`~~
    - Kind of difficult to do, since we don't have a model with metadata yet at time of `upload_to=` function
- [x] Remove bulk upload ui now that sftp works
- [x] On status page, move server uptime with some less pertinent details like version, etc below the source list
- [x] first name, last name => single field (dj name or display name)
- [x] SFTP audio asset playlists based on first folder instead of a user preference
- [x] way to convert asset types, potentially using https://github.com/ninemoreminutes/django-admin-object-actions
- [x] After asset.file.save(..., save=False) is called file is created, whether we create the asset or not
    - `django-unused-media` good candidate, but may interfere with constance's file fields
- [x] Admin css for input type=file busted
- [ ] Protect assets via nginx's `internal;` flag
- [ ] Skips to playout log
- [x] Don't use JSON field for show times so we get each show individually for status page and get show names
    - [x] Update user iteration hack in webui/views.py:StatusView.get_upcoming_status_data()

## Future Version

- [ ] Archiving of shows
- [x] Show live info about zoom on status page, similar to `dj_harbor_source` + `live_user` in status JSON
- [ ] S3 as a storage source using [django-storages](https://django-storages.readthedocs.io/)
- [ ] Compression and normalization on a per-DJ basis. (Add a liquidsoap `switch()` to
    change between compressed or not). Hard part is what are the rules for triggering this?
- [ ] Move liquidsoap harbor source editing into webui, but we could still only link it from admin.
    Remove `@admin.site.register_view()`, associated code, and simplify admin links.
    Rename _"Miscellaneous Configuration"_ to _"Additional Modules"._ Rethink how admin nav links are generated.
- [ ] Radio buttons for ban times
- [ ] Stock error pages for nginx, in particular if app doesn't boot
- [ ] Record shows on the calendar, or just record everything
    - S3 storage will come in handy at that point
- [ ] public API
- [ ] Get fancy with stopsets, create a telnet requests queue for them specifically so they get
    scheduled on time. Could use something similar for autodj requests. Would be a track sensitive fallback:
        1. stopsets via `requests.queue()`, these happen on a timer in liquidsoap or from huey
        2. autodj requests via `requests.queue()` happen the web UI (do we need some way to cap them?)
        3. regular autodj via `request.dynamic.list()`
- [ ] Ban DJs dynamically on the ban page (not just live ones) using select2

## Down the line

- [ ] Stop using Django admin, instead roll everything on our own.
    - [Halfmoon](https://gethalfmoon.com) looks pretty slick.
    - Use [alpine.js](https://github.com/alpinejs/alpine) as mini-framework for reactive front-end, not jQuery
- [ ] user preference for harbor auth = always to be kicked off at the end of their show anyway
