# Crazy Arms Radio Backend

## Introduction

Crazy Arms Radio Backend is a flexible and fully featured Internet radio back-end
written from the the ground up.

Think of Crazy Arms as a robot taking several inputs and deciding which one is
best to broadcast from. (Read more about precedence-based streaming below).

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


## Features

### Live Scheduling via Google Calendar

Scheduling of live DJs using Google Calendar. An invite to a calendar event means
a DJ is authorized to play. Simple as that.

### Scheduled playout of long-format audio files, ie prerecorded shows.

### Broadcasting for non-technical users with [Zoom](https://zoom.us/).

This is implemented with Zoom for Linux using a Docker container, so it's
inherently a bit brittle, but can be troubleshooted in a web browser by an admin.

###. _Idiot tolerant DJing._

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

* **THIS README**
* Docs: Initial setup
    - env file
    - docker build
* Docs: Account creation
* Docs: Static deploy?
* Docs: Updating section (Similar to AzuraCast self-update)
    - docker re-build
    - migrations
* Liquidsoap interactive telnet container, similar to container logs
    - https://github.com/nirui/sshwifty
* Use this [Go supervisord implementation](https://github.com/ochinchina/supervisord)


## Quick Setup

Make sure Docker + docker-compose is installed (Docker Desktop on macOS).

To start CARB,

```
git clone git@github.com:dtcooper/carb.git
cd carb
./compose.sh up
```

Then in your browser go to http://localhost/

To stop, press `CTRL+C`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
