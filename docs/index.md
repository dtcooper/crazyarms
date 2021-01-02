# Crazy Arms Radio Backend

!!! danger "Danger: Hic Sunt Dracones (Here Be Dragons)"
    Crazy Arms is currently **under active development**, however you can preview
    things right now.

    This documentation is a **work in progress.** There are missing sections, and
    it may include incorrect information until the first release.

Crazy Arms Radio Backend is a flexible and fully featured Internet radio back-end
written from the ground up.

It's specifically written after its author built a few _fully decentralized_
online radio stations with some common needs, but found no existing product fit.
Crazy Arms seeks to fit those needs needs out of the box, but allows for
stations to customize their stream if necessary to fit their unique use cases.

## Installation

If you're a technical user or a systems administrator wanting to install Crazy
Arms, head over to the [installation instructions](./server-setup.md#installation).

## Audio Infrastructure Overview

### Sources, Harbor, and Upstreams Explained

#### The Harbor

The main audio component of Crazy Arms is called the **Harbor.** It takes care
of choosing what to broadcast based on some simple rules. In a sense, it's a
stream picker. Think of the Harbor as a robot sitting at an imaginary console,
deciding what to play and when, using its _crazy arms_ turning volume knobs, and
pushing and pulling on faders at exactly the right moment. _(And just like that,
we arrive at the reason for the project's name! Okay, it's not the
[only reason...](https://www.youtube.com/watch?v=GurizZaR0Ms))_

#### Sources

The harbor has several input **sources.** A source is any audio input feeding
into the harbor. In our robot example above, think of sources as input channels
on the console. Out of the box examples of sources include the
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
    it. What exactly constitutes _active_ and _inactive?_ The answer is that it
    depends on the source.

    For example, in the case of the AutoDJ source, Crazy Arms will always have
    music to play so that source is always considered to be active. _(You did
    upload music into the AutoDJ, right!?)_ The AutoDJ has low priority so it's
    sort of an always-on default.

    On the other hand, take a "live source" like a live DJ streaming using
    Icecast 2. When the DJ connects and starts streaming, that source is active.

    That's not the whole story. The harbor uses **silence detection** for live
    sources. This means if a live DJ is connected and streaming, but is
    broadcasting silence the source is considered inactive. Suppose their
    microphone isn't working or a fader on their mixer is accidentally pulled
    down. Or maybe they forgot to disconnect. We wouldn't want your station
    silent, would we? In short, if a live source is connected but silent, it will
    be considered inactive. The amount of silence before fading is configurable
    {# TODO: reference constance -#}
    but defaults to 15 seconds.

    The theory behind this feature is part of the **_Idiot-Tolerant(tm)_ DJing**
    philosophy of Crazy Arms. :wink:

!!! hint "The Failsafe, the _Real_ Always-on Default"
    Remember when I called the AutoDJ an "always-on default" just a couple
    paragraphs ago. Well, the AutoDJ _can be disabled or end up in an erroneous
    state,_ for example if it chokes up on an invalid audio file[^1], or you
    start deleting music off the disk. If that happens, the AutoDJ will be an
    inactive source and as noted above Crazy Arms doesn't like to broadcast silence.

    For this reason, it's not _really_ the always-on default source with the
    lowest priority. It just acts like it. Enter, the **failsafe.** This
    is a track that plays on simple repeat. The preloaded track is ridiculously
    annoying hold music but can be changed using the Station Configuration
    module in the station admin site.

[^1]:
    Crazy Arms tries very hard to reject invalid audio files, but it is
    theoretically possible for it happen. In this case the AutoDJ could
    temporarily fail and become inactive for a short time.

#### Upstream Servers

The last thing you need to know about are we Crazy Arms called **upstream servers.**
These are simply places where your station is being broadcast to, usually Icecast
2 servers. That's where listeners connect to. They're the final output of the
Harbor. Some radio automation suites call these _"encoders."_ These might be
remote partners like [iHeart](https://www.iheart.com/) or [SiriusXM](http://siriusxm.com),
a streaming provider like [StreamGuys](https://www.streamguys.com/), or your own
infrastructure. You can configure as many upstream servers as you like. For
convenience and to kickstart your station, Crazy Arms bundles a local Icecast 2
server it streams MP3 at `128kbps` to by default, using the popular
[icecast-kh](https://github.com/karlheyes/icecast-kh) branch.

#### Harbor Flow Diagram

Now that you understand the basic concepts with the Harbor, here's what it looks
like.

!!! note "Harbor Flow Diagram"

    ```mermaid
    flowchart LR
        subgraph sources ["Priority-Based Sources"]
            prerecord("1. Pre-recorded Broadcast<br>(Scheduled, long-format shows)")
            subgraph live-sources ["Live Sources (Silence Detection)"]
                dj("2. Live DJ<br>(Icecast 2, RTMP)")
                zoom("3. Live Zoom Room<br>(if available)")
            end
            autodj("4. AutoDJ<br>(if available)")
            failsafe(5. Failsafe)
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

{#- TODO: these could be snippets, available to certain page #}

=== "Pre-recorded Broadcasts"
    !!! important "Source Details"
        |    |    | {# Hack to have an empty header #}
        | -: | :- |
        | Priority: | 1 (highest)
        | Silence Detection: | Disabled :material-close:
        | Description: | Audio uploaded into the station admin site, then scheduled for airplay at a specific time.
        | Availability: | Pre-recorded broadcasts are _always available_ in Crazy Arms to users with the _Program and schedule pre-recorded broadcasts_ permission.
        | Example: | Two hour show recorded to an mp3 called `friday_night_mix.mp3`. This file is uploaded into the web UI by Alison Administrator on Monday, where she then schedules it to air Tuesday from 9:00pm to 11:00pm.

=== "Live DJ"
    !!! important "Source Details"
        |    |    |
        | -: | :- |
        | Priority: | 2
        | Silence Detection: | Enabled :material-check:
        | Description: | Live DJ streaming using either Icecast 2 or RMTP.
        | Availability: | The ability to live DJ is _always available_ to users provided they are [authorized on the harbor](admin-guide/permissions.md#harbor-authorization).
        | Example: | Diana Disk Jockey uses [Audio HiJack](https://rogueamoeba.com/audiohijack/) from her Macbook to broadcast a live show with USB microphone and iTunes on Wednesday from 6:00pm to 8:00pm.

=== "Zoom Room"
    !!! important "Source Details"
        |    |    |
        | -: | :- |
        | Priority: | 3
        | Silence Detection: | Enabled :material-check:
        | Description: | Live streaming using a Zoom room.
        | Availability: | The ability to use a Zoom room is _only available_ if it is enabled for your installation ([`ZOOM_ENABLED=1` in your `.env` file](admin-guide/configuration/#the-environment-file-env-static-settings)). Furthermore it is only available to users provided they are [authorized on the harbor](admin-guide/permissions.md#harbor-authorization).
        | Example: | Video Conference Charlie starts a [Zoom room](https://zoom.us), enters the room link into Crazy Arms web interface and click start for one hour broadcast at 10:00am on Thursday.

=== "AutoDJ"
    !!! important "Source Details"
        |    |    |
        | -: | :- |
        | Priority: | 4
        | Silence Detection: | Disabled :material-close:
        | Description: | Audio uploaded into the station admin site that plays at random. [More information here](admin-guide/autodj.md).
        | Availability: | The autodj is _available_ if the [station configuration `AUTODJ_ENABLED` is set to `True`](admin-guide/configuration/#autodj-configuration), which is the default.
        | Example: | Steel Guitar Sally uploads the entire Ray Price catalog to the AutoDJ through the station admin site so music from that plays except during for the shows with higher priority scheduled on Tuesday, Wednesday and Thursday.

=== "Failsafe"
    !!! important "Source Details"
        |    |    |
        | -: | :- |
        | Priority: | 5 (Lowest, always available)
        | Silence Detection: | Disabled :material-close:
        | Description: | Audio that plays when nothing else is available. (You'll likely only to hear this if the AutoDJ is disabled.)
        | Availability: | The failsafe is _always on._ That's kind of the point, right?
        | Example: | Station Manager Mike Bob disabled the AutoDJ for the radio station. When no one is streaming a live show, the failsafe track plays on repeat. Listeners are probably annoyed! For shame, Mike!


### Customization & Settings

The Harbor is customizable. There are several settings you can choose from and
technical users can add additional sources or program the Harbor to do all sorts
of novel things. This level of customization, while for advanced users, is an
important feature of Crazy Arms. Every station is different some may have
nonstandard cases, so there may be no one size fits all
solution for everyone.

If you're an administrator, find out how to customize the Harbor by
[reading more here](admin-guide/configuration.md).

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
    adoption and east of use --- and implementation of recurring events.. Your
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

station admin site Look and Feel
:   The station admin site for Crazy Arms has a fairly inflexible look and feel. It's
    not necessarily a beautiful, easy to use interface but instead meant for
    somewhat technical users. This is by design and was chosen for ease of
    programming. The technical reason for why is that we chose to build it on
    top of [Django's admin module](https://docs.djangoproject.com/en/3.1/ref/contrib/admin/)
    module.
