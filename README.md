# Crazy Arms Radio Backend

## Introduction

Crazy Arms Radio Backend is a flexible and fully featured Internet radio back-end
written from the ground up.

Think of Crazy Arms as a robot taking several inputs (sources) and deciding which
one is best to broadcast from based on a hierarchy or precedence. (Read more about
precedence-based streaming below).

It's specifically written after its author
built several _fully decentralized_ online radio stations with varied types of
scheduling and finding no existing product fit some common needs out of the box.

## Quickstart

***Crazy Arms is currently under active development, however you can preview
things right now by doing the following.***

Prerequisite: Linux or macOS with [Docker](https://www.docker.com/) and
[docker-compose](https://docs.docker.com/compose/) installed.


Clone the repo and start the code. Building the containers may take a few
minutes.

```
git clone git@github.com:dtcooper/carb.git
cd carb
./compose.sh up
```

Then in your browser go to http://localhost/. To stop, press `CTRL+C`.

## Unit Tests

To run the unit tests, use the shell `compose.sh` script as follows,

```
./compose.sh test

# Tear down test dependent containers (postgres and redis)
./compose --test down
```

## Features

### Live Scheduling via Google Calendar

Scheduling of live DJs using Google Calendar. An invite to a calendar event means
a DJ is authorized to play. Simple as that.

### Scheduled playout of long-format audio files, ie prerecorded shows.

### Broadcasting for non-technical users with [Zoom](https://zoom.us/).

This is implemented with Zoom for Linux using a Docker container, so it's
inherently a bit brittle, but can be troubleshooted in a web browser by an admin.

### _Idiot tolerant DJing._

If a live DJ is broadcasting silence, Crazy Arms picks another input to stream
from.

### Completely [Docker](https://www.docker.com/)-ized

Easy development and easy deployment.

### Precedence-based streaming

### Useful and informative station administration and status tools.

### Uploading audio from varied sources

Uploading of audio files from sources like [SoundCloud](https://soundcloud.com/),
[Mixcloud](https://www.mixcloud.com/), or [YouTube](https://www.youtube.com/) are
supported. Just enter a URL and the Crazy Arms downloads and processes your audio file.

This utilizes the wonderful [youtube-dlc](https://github.com/blackjack4494/yt-dlc)
tool and supports literally
[_thousands of sites_](https://github.com/blackjack4494/yt-dlc/blob/master/docs/supportedsites.md)!

### An AutoDJ that plays blocks of advertisements and station IDs.

### Fine-grained user permission structure.

### Accessible Logs

Less technical users can see server logs without `ssh` or command-line knowledge.

### Streaming Customization
At your own risk, you can modify [Liquidsoap](https://www.liquidsoap.info/)
broadcasting scripts.


## TODOs

1. **THIS README** + docs
    - Initial setup
    - env file
    - docker build process + describing `./compose.sh` + `overrides.yml`
1. ~~AutoDJ~~ - _done!_
    - Playlists
    - Ad rotators
    - Weighting similar to [Tomato](https://github.com/dtcooper/tomato)
    - [select2](https://django-easy-select2.readthedocs.io/) AutoDJ requests in
      webui (add a new list redis that gets popped from
1. Finish Zoom broadcasting
1. Potential for S3 as a storage source using
   [django-storages](https://django-storages.readthedocs.io/)
1. Clean up Dockerfiles stripping dev stuff
1. Go over `TODO`s and `XXX`s in codebase
1. Unit tests for at least the Django app
    - Skeleton for tests is _done!_
1. Mature `strip_blank` implementation
1. Convert some Django views to class-based
    - ~~api~~ - _done!_
    - webui
1. ~~Player for local icecast on status page~~ - _done!_
1. ~~Make track log a more generic playout log, with asset playing on metadata one
   particular type.~~ - _done!_
1. Pin versions in all Dockerfiles, and Python packages
    (using [Poetry](https://python-poetry.org/))
1. Convert logging to redis queue (so web server doesn't have to be up to log)
1. ..._and more!_

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
