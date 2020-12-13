# Crazy Arms Radio Backend

Crazy Arms Radio Backend is a flexible and fully featured Internet radio back-end
written from the ground up.

It's specifically written after its author built a few _fully decentralized_
online radio stations with varying types of scheduling and finding no existing
product fit some common needs out of the box.

Read the [documentation for Crazy Arms here](https://dtcooper.github.io/carb).

## Technical TODOs

1. **THIS README** + docs
    - Initial setup
    - env file
    - docker build process + describing `./compose.sh` + `overrides.yml`
1. ~~AutoDJ~~ - _done!_
    - ~~Playlists~~
    - ~~Ad rotators + stopsets~~
    - ~~Weighting similar to [Tomato](https://github.com/dtcooper/tomato)~~ -
      playlists are weighted, which should be enough
    - [select2](https://django-easy-select2.readthedocs.io/) AutoDJ requests in
      webui (add a new list redis that gets popped from
1. ~~Finish Zoom broadcasting~~ - _done!_
1. Potential for S3 as a storage source using
   [django-storages](https://django-storages.readthedocs.io/)
1. Clean up Dockerfiles stripping dev stuff
1. Go over `TODO`s and `XXX`s in codebase
1. Unit tests for at least the Django app
    - Skeleton for tests is _done!_
1. ~~Mature `strip_blank` implementation~~ - _done!_
1. Convert some Django views to class-based
    - ~~api~~ - _done!_
    - webui
1. ~~Player for local icecast on status page~~ - _done!_
1. ~~Make track log a more generic playout log, with asset playing on metadata one
   particular type.~~ - _done!_
1. Pin versions in all Dockerfiles, and Python packages
  (using [Poetry](https://python-poetry.org/))
1. ~~Convert logging to redis queue (so web server doesn't have to be up to log)~~ - _done!_
   (used `psql` to directly insert into the DB)
1. ~~Kick off DJs outside of calendar times (with a grace period)~~
1. TIME REMAINING of Zoom Show
1. Add streaming instructions page for users
1. Add make active/disable quick actions for playlists and stopsets
1. Schedule stopsets at specific times - necessary? nice-to-have
1. Compression and normalization on a per-DJ basis. (Add a liquidsoap `switch()` to
  change between compressed or not). Hard part is what are the rules for triggering this?
1. Add time to scheduled broadcasts
1. Include this readme as part of build and link to it with HELP button
1. Define harbor in glossary
1. Indication about why the zoom form doesn't show for calendar based auth
1. Hide skip track button for lower precedence sources
1. Radio buttons for ban times
1. Copy change: rename "precedence" -> "priority"
1. Edit profile seems to have re-enabled harbor access type
1. Thoroughly test new ffprobe + ffmpeg flows for audio assets + task
1. Convert uploads into their own model.
1. ~~Harbor: use an add_timeout poll to check for `status_json()` changes rather than
  hooks `update_status[_ref]()` hooks throughout the code.~~ - _done!_
1. GCal shows stored as `JSONField` with show name, useful for Zoom or Liquidsoap metadata
1. ..._and more!_
## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
