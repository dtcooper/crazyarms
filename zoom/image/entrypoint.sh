#!/bin/sh

# Make sure /etc/skel is copied over to user's home
su - user -c 'cp -r /etc/skel/. /home/user'
exec $@
