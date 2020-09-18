# BMIR 2020 Stream Code

Here's the code that powers [Burning Man Informatio Radio's](https://bmir.org)
2020 stream.

## Harbor

Found in the `harbor/` folder.

Here is the script that runs the stream preference automation. The output of this
stream comes from one of the following from a basic hierarchy.

1. **[Most preferred]** A "priority" [Icecast 2](https://icecast.org/) mount for 
   pre-recorded shows to  stream to, as well as for administrators to take over
   the stream, if needed.
2. An [Icecast 2](https://icecast.org/) mount for DJs remote stream to. Silence
   being broadcast on this stream will be treated as if a DJ is not connected
   after 25 seconds.
    * The `live` stream accepts passwords from a Google Sheet that authenticates
      passwords (and kicks people off) based on time intervals.
    * The `test` stream accepts a fixed passwords, does not kick people off, and
      will also accept password from the spreadsheet for testing.
3. [PulseAudio](https://www.freedesktop.org/wiki/Software/PulseAudio/) input.
   This will be the dummy device monitor output of a [Zoom](https://zoom.us/)
   room running inside [Xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml)
   using [icewm](https://ice-wm.org/) as a window manager. Silence on this input
   will be treated as if the stream is down.
4. An autoDJ rotating tracks from disk mixed in with station ID and ad blocks
   every so often.

You can use Docker to test this, however the script runs without Docker on an
Ubuntu 20.04 machine.

### To run the harbor

Copy over the environment configuration file and edit it.

```bash
cd harbor
cp env.vars.default env.vars
```

If you have liquidsoap installed on a Linux machine OR if you have
[Docker](https://www.docker.com/) on macOS, run,

```bash
./run.sh
```

The most important open ports are:
* `8000`: The [Icecast 2](https://icecast.org/) server to listen to the stream.
   See the status page at http://localhost:8001/
* `8001`: The [liquidsoap](https://www.liquidsoap.info/) harbor script.
   * Stream to mounts `/stream` or `/priority` (as above) with default password `hackme`
   * View the harbor status page by going to http://localhost:8001/, default password is `hackme`.
* `80`: [nginx](https://nginx.org/) + [noVNC](https://novnc.com/info.html), with
  a desktop environment with Zoom installed. You can test out [Zoom](https://zoom.us/)
  streaming with the [PulseAudio](https://www.freedesktop.org/wiki/Software/PulseAudio/)
  input described above by going to http://localhost/ and opening Zoom.
* `1234`: Telnet monitor of the harbor script.
    * Try connecting and sending `help` + enter for more info.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
