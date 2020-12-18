# Crazy Arms Radio Backend

Crazy Arms Radio Backend is a flexible and fully featured Internet radio back-end
written from the ground up.

It's specifically written after its author built a few _fully decentralized_
online radio stations with varying types of scheduling and finding no existing
product fit some common needs out of the box.

Read the [documentation for Crazy Arms here](https://dtcooper.github.io/carb).

## Technical TODOs

- [ ] Documentation - _underway using mkdocs_
    - [x] Initial setup
    - [ ] env file
    - [ ] docker build process + describing `./compose.sh` + `overrides.yml`
    - [ ] Add streaming instructions page for users
    - [ ] AutoDJ weighting concept
    - [ ] Harbor architecture and concepts
- [ ] AutoDJ
    - [x] Playlists
    - [x] Ad rotators + stopsets
    - [x] Weighting similar to [Tomato](https://github.com/dtcooper/tomato) (playlists are weighted,
      which should be enough)
    - [x] [select2](https://django-easy-select2.readthedocs.io/) requests in webui (add a new list in
        redis that gets popped from?)
    - [ ] sse live status component of AutoDJ requests
- [x] Finish Zoom broadcasting
    - [ ] needs a second pass, and a better show length picker
- [ ] Potential for S3 as a storage source using [django-storages](https://django-storages.readthedocs.io/)
- [ ] Clean up Dockerfiles stripping dev stuff
- [ ] Go over `TODO`s and `XXX`s in codebase
- [x] Unit tests for at least the Django app - _skeleton done_
    - [ ] major second pass, fix broken tests, aim for high coverage _(or 100%)
- [x] Mature `strip_blank` implementation
- [ ] Convert some Django views to class-based
    - [x] `api` package
    - [ ] `webui` package
- [x] Player for local icecast on status page
- [x] Make track log a more generic playout log, with asset playing on metadata one
    particular type.
- [ ] Pin versions in all Dockerfiles, and Python packages
    (using [Poetry](https://python-poetry.org/))
- [x] Convert logging to redis queue (so web server doesn't have to be up to log)
    (decided to use `psql` to directly insert into the DB)
- [x] Kick off DJs outside of calendar times (with a grace period)
- [ ] TIME REMAINING of Zoom Show
- [ ] Add make active/disable quick actions for playlists and stopsets
- [ ] Schedule stopsets at specific times - necessary? nice-to-have
- [ ] Compression and normalization on a per-DJ basis. (Add a liquidsoap `switch()` to
    change between compressed or not). Hard part is what are the rules for triggering this?
- [x] Add scheduled time inline to broadcasts asset creation
- [ ] Indicator about why the zoom form doesn't show for calendar based auth
- [x] Hide skip track button for lower precedence sources
- [ ] Radio buttons for ban times
- [x] Copy change: rename "precedence" -> "priority"
- [ ] BUG: Edit profile seems to have re-enabled harbor access type
- [x] Thoroughly test new ffprobe + ffmpeg flows for audio assets + task
- [ ] ~~Convert uploads into their own model.~~ - _not doing this._
- [x] Harbor: use an add_timeout poll to check for `status_json()` changes rather than
    hooks `update_status[_ref]()` hooks throughout the code.
- [ ] GCal shows stored as `JSONField` with show name, useful for Zoom or Liquidsoap metadata
    - am I sure I want this??? :tongue:
- [ ] Tasks to purge failed broadcasts/assets + unstuck processing ones
- [x] Re-try broadcasts for which underlying assets which aren't `READY` every 2 seconds.
    Fix asset's inline broadcasts.
- [ ] Remove `sse` service and use the nginx package in Ubuntu 20.04 container,
    which has the [nchan](https://nchan.io/) module in the
    [extras package](https://packages.ubuntu.com/bionic/nginx-extras).
- [ ] Add sftp service using sftpgo

..._and more!_

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
