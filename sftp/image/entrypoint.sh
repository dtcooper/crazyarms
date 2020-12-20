#!/bin/sh

mkdir -p /config/sftp
cd /var/lib/sftpgo
cp -v /etc/sftpgo.json sftpgo.json

if [ ! -f id_rsa ]; then
    echo 'Generating an ssh key for sftp/scp'
    ssh-keygen -t rsa -b 4096 -f id_rsa -q -N ""
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
else
    exec sftpgo serve
fi
