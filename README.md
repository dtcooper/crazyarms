# Crazy Arms Radio Backend &mdash; :zany_face: :mechanical_arm: :radio: :woman_technologist:

Crazy Arms Radio Backend is a flexible and fully featured Internet radio back-end
written from the ground up.

It's specifically written after its author built a few _fully decentralized_
online radio stations with varying types of scheduling and finding no existing
product fit some common needs out of the box.

Read the [documentation for Crazy Arms here](https://dtcooper.github.com/crazyarms).


## Quickstart

1. Install [Docker](https://www.docker.com/) and
    [docker-compose](https://docs.docker.com/compose/). On macOS, install
    [Docker for Mac](https://docs.docker.com/docker-for-mac/install/).
    On Debian/Ubuntu do the following:

    ```
    # Install Docker (Linux instructions only)
    curl -fsSL https://get.docker.com | sh

    # and docker-compose
    sudo curl \
        -L "https://github.com/docker/compose/releases/download/1.29.0/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

    # (If you're a non-root user)
    sudo adduser "$USER" docker
    # Log back in and out, to make sure you're in the docker group
    ```

2. Clone Crazy Arms,

    ```
    git clone https://github.com/dtcooper/crazyarms.git
    ```

3. Run the thing docker-compose wrapper script `./compose.sh` to configure and
    pull Crazy Arms.

    ```
    cd crazyarms

    # This will ask you some basic questions. For local development domain
    # name should be the default of "localhost"
    ./compose.sh pull
    ```

    If you want to change any of these settings, edit the `.env` file in the
    project directory. (NOTE: A later release will have these containers built
    and downloadable from [Docker Hub](https://hub.docker.com/).)

    (For development only, to build containers from source, run `./compose.sh build`
    instead of `pull` above. This may take a while.)

4. Start Crazy Arms

    ```
    ./compose.sh up -d
    ```

5. In your web browser, go to the domain name you chose, ie <http://localhost/>.

#### [Digital Ocean](https://www.digitalocean.com/) Notes

* A 2gb + 2 CPU droplet or better is recommended if you're using Zoom, otherwise
  the cheapest one will do.
* [haveged](http://www.issihosts.com/haveged/) makes docker-compose run
    significantly faster:

    ```
    sudo apt-get install -y haveged
    ```

#### Apple M1 Chipset Notes (aarch64)

It works with the [Docker for Mac Apple M1
preview](https://docs.docker.com/docker-for-mac/apple-m1/)!
However, native `aarch64` containers are not provided, so you'll need to build
them from source (`./compose.sh build` instead of `pull`). The Zoom container
will need to emulate amd64.

## Liquidshop 1.0 Slide Deck

Here's [a slide deck](https://docs.google.com/presentation/d/18K1RagpDW79u086r2EV_ysAzFR9gkGJiZTk1cOZCUTg/edit?usp=sharing)
about Crazy Arms from the [Liquidshop 1.0](https://liquidsoap.info/liquidshop) conference
giving a high level overview and some of the technical approaches taken.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
