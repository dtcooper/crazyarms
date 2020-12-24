# Crazy Arms Radio Backend

!!! danger "Crazy Arms is under active development"
    Crazy Arms is currently under active development, however you can preview
    things right now. This documentation is incomplete, is missing sections, and
    may include incorrect information until the first release.

Crazy Arms Radio Backend is a flexible and fully featured Internet radio back-end
written from the ground up.

It's specifically written after its author built a few _fully decentralized_
online radio stations with varying types of scheduling and finding no existing
product fit some common needs out of the box.

If you're an technical user or a systems administrator wanting to install Crazy
Arms, head over to the [installation instructions](./server-setup.md#installation).

## Audio Infrastructure Overview

### Sources, Harbor, and Upstreams Explained

#### The Harbor

The main audio component of Crazy Arms is called the **Harbor.** It takes care
of choosing what to broadcast based on some simple rules. In a sense, it's a
stream picker. Think of the Harbor as a robot sitting at an imaginary console,
deciding what play and when, using its _crazy arms_ turning volume knobs, and
pushin' and pullin' on faders at exactly the right moment. _(And just like that,
we arrive at the reason for the name! Okay, it's not the
[only reason...](https://www.youtube.com/watch?v=GurizZaR0Ms))_

#### Sources

The harbor has several input **sources.** A source is any audio input feeding
into the harbor. In our robot at the console example above, think of sources as
input channels on the console. Out of the box examples include the
[AutoDJ](users-guide/autodj.md),
[scheduled, pre-recorded broadcasts](users-guide/prerecorded-broadcasts.md),
and live DJs streaming with [Icecast 2](users-guide/dj/icecast.md),
[RTMP](users-guide/dj/rtmp.md) (experimental), or a [Zoom room](users-guide/dj/zoom.md).
Each input is assigned a priority, and the source with the highest priority
_that is active_ will be what the robot chooses to play. We call this concept
**priority-based streaming.**

!!! info "Active and Inactive Sources, Silence Detection"
    {# TODO: link "smoothly fade" to that setting #}
    When a source goes from inactive to active, the Harbor will smoothly fade to
    it. What exactly constitutes _active_ and _inactive_ depends on the source?

    For example, in the case of the AutoDJ source, Crazy Arms will always have
    music to play so that source is always considered to be always active.
    _(You did upload music, right?)_ The AutoDJ has low priority so it's sort of
    an always-on default.

    On the other hand, take a "live source" like a live DJ streaming using
    Icecast 2. When the DJ connects and starts streaming, that source is active.

    That's not the whole story. The harbor uses **silence detection** for live
    sources. This means if a live DJ is connected and streaming, but is
    broadcasting silence the source is considered inactive. Suppose their
    microphone isn't working or a fader on their mixer is accidentally pulled
    down. Or maybe they forgot to disconnect. We wouldn't want your station
    silent, would we? In short, if a live source is connected but silent, it will
    be considered inactive. The amount of silence before fading is configurable
    {# TODO: reference constance #}
    but defaults to 15 seconds.

    The theory behind this feature is part of the _Idiot-Tolerant(tm)_ DJing
    philosophy of Crazy Arms. :wink:

#### Upstream Servers

The last thing you need to know about are we Crazy Arms called **upstream servers.**
These are simply places where your station is being broadcast to, usually Icecast
2 servers. That's where listeners connect to. They're the final output of the
Harbor. Some radio automation suites call these _"encoders."_ These might be
remote partners like [iHeart](https://www.iheart.com/) or [SiriusXM](http://siriusxm.com),
a streaming provider like [StreamGuys](https://www.streamguys.com/) or your own
infrastructure. You can configure as many upstream servers as you like. For
convenience and to kickstart your station, Crazy Arms bundles a local Icecast 2
server it streams MP3 at `128kbps` to by default, using the popular
[icecast-kh](https://github.com/karlheyes/icecast-kh) branch.

#### Harbor Flow Diagram

Now that you understand the basic concepts with the Harbor, here's what it looks
like.

???+ note "Harbor Flow Diagram"

    ```mermaid
    flowchart LR
        subgraph sources ["Priority-Based Sources"]
            prerecord("1. Pre-recorded Broadcast<br>(Scheduled, long-format shows)")
            subgraph live-sources ["Live Sources (Silence Detection)"]
                dj("2. Live DJ<br>(Icecast 2, RTMP)")
                zoom("3. Live Zoom Room<br>(optional)")
            end
            autodj("4. AutoDJ<br>(optional)")
            failsafe(5. Failsafe Audio File)
        end

        harbor(("Harbor<br>(Intelligent stream picker)"))

        prerecord -->|highest priority| harbor
        dj --> harbor
        zoom --> harbor
        autodj --> harbor
        failsafe -->|lowest priority| harbor

        subgraph upstreams ["Upstream Servers"]
            icecast1("Local Icecast 2 Server (mp3)")
            icecast2("External Icecast 2 Server (aac)")
            icecastOthers("Other Icecast 2 Servers")
        end

        harbor --> icecast1
        harbor --> icecast2
        harbor --> icecastOthers

        listeners(("Listeners"))

        icecast1 --> listeners
        icecast2 --> listeners
        icecastOthers --> listeners
    ```

#### Sources Details

| **Priority** | **Source**              | **Silence Detection ** | **Description**                                                                                               | **Example**                                                                                                                                     | **Optional**     |
| -----------: | :---------------------- | :--------------------: | :------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------------------------------------------------------------------------------- | :--------------: |
| 1            | Pre-recorded Broadcasts | :material-close:       | Audio uploaded into the admin site, then scheduled for airplay at a specific time.                            | MP3 of a two hour show called _Friday Night Mix_ uploaded on Thursday and scheduled to air Friday from 9:00pm to 11:00pm.                       | :material-close: |
| 2            | Live DJ                 | :material-check:       | Live DJ streaming using either Icecast 2 or RMTP.                                                             | Jane uses [Audio HiJack](https://rogueamoeba.com/audiohijack/) from her laptop to broadcast a live two hour show Wednesday at 6:00pm.           | :material-close: |
| 3            | Zoom Room               | :material-check:       | Live streaming using a Zoom room.                                                                             | John starts a Zoom room, enters the room link into Crazy Arms web interface and starts a one hour broadcast at 10:00am on Saturday.             | :material-check: |
| 4            | AutoDJ                  | :material-close:       | Audio uploaded into the admin site that plays at random.                                                      | Sally uploads the entire Ray Price catalog to the AutoDJ through the admin site so music from that plays except during the above shows.         | :material-check: |
| 5            | Failsafe Audio          | :material-close:       | Audio that plays when nothing else is available. (You'll likely only to hear this if the AutoDJ is disabled.) | Bob disabled the AutoDJ for the radio station. When no one is streaming a live show, the failsafe track plays on repeat. Listeners are annoyed! | :material-close: |


### Customization

Behind the scenes, the Harbor is a highly customizable script, implemented in
[Liquidsoap](https://www.liquidsoap.info/). Technical users can add additional
sources or program the Harbor to do all sorts of novel things. This level of
customization, while for advanced used, is an important feature of Crazy Arms.
Ever station is and its use case are different, so there may be no one size fits
all solution for everytone.

## Features At a Glance

Priority-based Streaming
:   Crazy Arms operates on the concept of priority. This means it chooses the
    source (audio input) that is streaming, properly operating, or online with
    the highest priority. For example, a live DJ takes priority over the AutoDJ.
    See [more info on this concept below](#sources-harbor-and-upstreams-explained).

Live scheduling via Google Calendar
:   Scheduling of live DJs using Google Calendar. An invite to a calendar event means
    a DJ is authorized to play. Simple as that.

    Rather than re-invent the wheel, Google Calendar was chosen because of its wide
    adoption and east of use &mdash; and implementation of recurring events.. Your
    web front-end can integrate with that, rather than a complex, custom API.

Scheduled playout of long-format audio files, ie prerecorded shows
:   A major use case is taking long-format audio files (ie two hours) and scheduling
    them to play at specific times, superseding the AutoDJ.

Broadcasting for non-technical users with [Zoom](https://zoom.us/)
:   This is implemented with Zoom for Linux using a Docker container. A "runner"
    bash script does its best to connect to a user's Zoom room and listen in.
    It's inherently a bit brittle, but can be troubleshooted somewhat easily in
    a web browser running [noVNC](https://novnc.com/info.html) by an admin.

_Idiot-Tolerant(tm)_ DJing
:   If a live DJ or Zoom room is broadcasting silence, Crazy Arms picks another
    source to stream from.

Completely [Docker](https://www.docker.com/)-ized
:   Easy development and easy deployment using
    [docker-compose](https://docs.docker.com/compose/).

Useful and informative station administration and status tools.
:   Leveraging [Django](https://docs.djangoproject.com/en/3.1/)'s admin
    interface much of Crazy Arms can be managed by administrators (or users with
    the necessary permissions).

    A status page is also provided that uses
    [server-sent events](https://en.wikipedia.org/wiki/Server-sent_events) in
    which the Harbor service script communicates directly with your web browser
    in real-time.

Uploading audio from varied sources
:   Uploading of audio files from sources like [SoundCloud](https://soundcloud.com/),
    [Mixcloud](https://www.mixcloud.com/), or [YouTube](https://www.youtube.com/) are
    supported. Just enter a URL and the Crazy Arms downloads and processes your audio file.

    This utilizes the wonderful [youtube-dlc](https://github.com/blackjack4494/yt-dlc)
    tool and supports literally
    [_thousands of sites_](https://github.com/blackjack4494/yt-dlc/blob/master/docs/supportedsites.md)!

An AutoDJ that plays blocks of advertisements and station IDs (stop sets)
:   This feature can optionally be enabled in the _"Server Settings > Configuration"_
    section.

Fine-grained user permission structure.
:   If a user is _not_ an administrator, there are several permission groups to
    allow them some administrative privileges.

Accessible Logs
:   Less technical users can see server logs without `ssh` or command-line knowledge
    to help troubleshoot. Maybe a DJ got their password wrong or tried to broadcast
    at the wrong time?

Streaming Customization
:   At your own risk, you can modify [Liquidsoap](https://www.liquidsoap.info/)
    Harbor scripts. This gives pretty high flexibility for various use cases.

RTMP Support (Experimental)
:   There's experimental support for RTMP, so anyone who's familiar with tools
    like [Open Source Broadcaster (OBS)](https://obsproject.com/) can stream to
    the harbor. Of course, video is discarded.

### Non-Features

_The following are non-features of Crazy Arms._

Front-end Not Included
:   Crazy Arms is designed to be a backend for your radio stream only. A user
    interface that includes calendars, a fancy stream player, and metadata
    isn't included.

Admin Site Look and Feel
:   The admin site for Crazy Arms has a fairly inflexible look and feel. It's
    not necessarily a beautiful, easy to use interface but instead meant for
    somewhat technical users. This is by design and was chosen for ease of
    programming. The technical reason for why is that we chose to build it on
    top of [Django's admin site](https://docs.djangoproject.com/en/3.1/ref/contrib/admin/)
    module.
