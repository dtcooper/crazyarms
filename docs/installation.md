# Installation Guide

This guide is intended for systems administrators only.

## Installation

### Quickstart

!!! danger "Crazy Arms is under development"
    Crazy Arms is currently under active development, however you can preview
    things right now by doing the following steps below. These will likely change
    after initial development is complete.

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

### Unit Tests

```
./compose.sh test

# Tear down test dependent containers (postgres and redis)
./compose --test down
```

## Upgrading

## Development

### Helpful Practices

* In `.env` set `DEBUG = True`
* `overrides.yml`
* `./compose.sh` development commands
