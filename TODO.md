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
- [x] GCal shows stored as `JSONField`
    - [ ] add show name to JSON, useful for Zoom or Liquidsoap metadata am I sure I want this??? :tongue:
    - [ ] scrap `gcal` package, moving to user model in `common` completely
- [ ] Tasks to purge failed broadcasts/assets + unstuck processing ones, clean sftpgo files
- [x] Re-try broadcasts for which underlying assets which aren't `READY` every 2 seconds.
    Fix asset's inline broadcasts.
- [x] Remove `sse` service and use nginx module [nchan](https://nchan.io/)
- [x] Add sftp service using sftpgo
    - [x] Deal with WinSCP's `.filepart` situation
    - [x] Add ability to use SSH authorized keys.
- [x] Rename uploads with valid contents but wrong extension (ie file that's an mp3 but named wav)
- [ ] User emails
    - [x] Users can update their email address in their profile (`EMAIL_ENABLED` + verification only)
    - [ ] Do we really need a postfix container? Can't we just configure Django to send email directly?
    - [ ] Create user flow that sends user an email (and possibly they fill out their details)
    - [ ] Consistent "From: " emails
- [x] rtmp streaming using nginx-rtmp
- [ ] huey logs seem to print twice / django logging seems overly verbose (maybe just in gunicorn?)
- [ ] use [multirun](https://github.com/nicolas-van/multirun) for nginx (nginx + certbot),
    and icecast (icecast + notify) containers
- [x] investigate whether asset models should use `clean()` or `full_clean()`?
    (Does it only matter with unique indexes?)
- [ ] "There were errors on this page" message for forms with errors at top of page. Possible mixin
    that adds a message when `form_invalid(...)`
- [ ] Don't organize assets by folder prefixes that say where they came from like `upload/`, `external/`, etc
    instead organize by `<artist-normalized-and-non-empty>/<album-normalized-and-non-empty>/`
- [ ] Remove bulk upload ui now that sftp works

## Future Version

- [ ] Show live info about zoom on status page, similar to `dj_harbor_source` + `live_user` in status JSON
- [ ] S3 as a storage source using [django-storages](https://django-storages.readthedocs.io/)
- [ ] Schedule stopsets at specific times - necessary? nice-to-have
- [ ] Compression and normalization on a per-DJ basis. (Add a liquidsoap `switch()` to
    change between compressed or not). Hard part is what are the rules for triggering this?
- [ ] Move liquidsoap harbor source editing into webui, but we could still only link it from admin.
    Remove `@admin.site.register_view()`, associated code, and simplify admin links.
    Rename _"Miscellaneous Configuration"_ to _"Additional Modules"._ Rethink how admin nav links are generated.
- [ ] Radio buttons for ban times
