#!/bin/sh

# Make sure /etc/skel is copied over to user's home
sudo -u user cp -nr /etc/skel/. /home/user
exec "$@"
