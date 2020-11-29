# Crazy Arms Radio Backend

## Introduction

Crazy Arms Radio Backend is a flexible and fully featured Internet radio back-end
written from the ground up.

It's specifically written after its author built several _fully decentralized_
online radio stations with varied types of scheduling and finding no existing
product fit some common needs out of the box.

## Quickstart

***Crazy Arms is currently under active development, however you can preview
things right now by doing the following.***

Prerequisite: Linux or macOS with [Docker](https://www.docker.com/) and
[docker-compose](https://docs.docker.com/compose/) installed.

In your terminal clone the repo and start the code. Building the containers may
take several minutes.

```
git clone git@github.com:dtcooper/carb.git
cd carb

./compose.sh up
```

You'll be asked a few questions about setting up Crazy Arms in your terminal.
When building is done, then in your browser go to
[`http://localhost/`](http://localhost/). You'll be prompted in the application
about setting up your station.

If you want a fairly preview of what the AutoDJ has to offer, be sure to select
_"Preload the AutoDJ"_ when setting up your station.

To stop, in your terminal press `CTRL+C`.

## Features at a Glance

### Precedence-based streaming

Crazy Arms operates on the concept of precedence. This means it chooses the
source (audio input) that is streaming, properly operating, or online with
the highest precedence. For example, a live DJ takes precedence over the AutoDJ.

Think of Crazy Arms as a robot taking several sources and deciding which
one is best to broadcast based on the rules you see on the status page.

### Live scheduling via Google Calendar

Scheduling of live DJs using Google Calendar. An invite to a calendar event means
a DJ is authorized to play. Simple as that.

### Scheduled playout of long-format audio files, ie prerecorded shows.

A major use case is taking long-format audio files (ie two hours) and scheduling
them to play at specific times, superseding the AutoDJ.

### Broadcasting for non-technical users with [Zoom](https://zoom.us/).

This is implemented with Zoom for Linux using a Docker container. A "runner"
bash script does its best to connect to a user's Zoom room and listen in. It's
inherently a bit brittle, but can be troubleshooted somewhat easily in a web
browser running [noVNC](https://novnc.com/info.html) by an admin.

### _Idiot tolerant DJing._

If a live DJ or Zoom room is broadcasting silence, Crazy Arms picks another
input to stream from.

### Completely [Docker](https://www.docker.com/)-ized

Easy development and easy deployment.

### Useful and informative station administration and status tools.

Leverage [Django](https://docs.djangoproject.com/en/3.1/)'s  admin interface,
much of Crazy Arms can be managed by administrators (or users with the necessary
permissions).

A status page is also provided that uses
[server-sent events](https://en.wikipedia.org/wiki/Server-sent_events) in which
the Liquidsoap (audio) script communicates directly with web clients in real-time.

### Uploading audio from varied sources

Uploading of audio files from sources like [SoundCloud](https://soundcloud.com/),
[Mixcloud](https://www.mixcloud.com/), or [YouTube](https://www.youtube.com/) are
supported. Just enter a URL and the Crazy Arms downloads and processes your audio file.

This utilizes the wonderful [youtube-dlc](https://github.com/blackjack4494/yt-dlc)
tool and supports literally
[_thousands of sites_](https://github.com/blackjack4494/yt-dlc/blob/master/docs/supportedsites.md)!

### An AutoDJ that plays blocks of advertisements and station IDs (stop sets)

This feature can optionally be enabled in the _"Server Settings > Configuration"_
section.

### Fine-grained user permission structure.

If a user is _not_ a superuser, there are several permission groups to allow
them some administrative privileges.

### Accessible Logs

Less technical users can see server logs without `ssh` or command-line knowledge
to help troubleshoot. Maybe a DJ got their password wrong or tried to broadcast
at the wrong time?

### Streaming Customization

At your own risk, you can modify [Liquidsoap](https://www.liquidsoap.info/)
broadcasting scripts. This gives pretty high flexibility for various use cases.

## Glossary of Terms

AutoDJ related
* **Audio asset** &mdash; audio files, music or short programming for AutoDJ
* **Playlist** &mdash; a collection of audio assets
* **Rotator** &mdash; a collection of stations IDs, PSAs, etc of the same category
* **Rotator asset** &mdash; a single audio
* **Stop set** &mdash; a "block" of rotators, stations IDs, PSAs, etc which in turn is really
  just a block one or more rotators.

## Unit Tests

To run the unit tests, which are currently a bit flaky, use the shell
`compose.sh` script as follows,

```
./compose.sh test

# Tear down test dependent containers (postgres and redis)
./compose --test down
```

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
1. ..._and more!_

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
