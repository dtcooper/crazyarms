FROM drakkan/sftpgo:alpine

USER root
WORKDIR /

RUN apk add --no-cache \
    curl \
    jq \
    openssh-keygen

RUN rm -rf /var/lib/sftpgo && ln -s /config/sftp /var/lib/sftpgo

COPY image/ /

ENTRYPOINT ["/entrypoint.sh"]
CMD []
