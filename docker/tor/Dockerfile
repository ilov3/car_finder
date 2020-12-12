FROM alpine:latest
RUN apk update && apk add tor privoxy supervisor --update-cache --repository http://dl-3.alpinelinux.org/alpine/edge/testing/ \
    && rm -rf /var/cache/apk/*
COPY torrc.default /etc/tor/torrc.default
COPY privoxy.default /etc/privoxy/config
ADD supervisor.conf /etc/supervisor.conf
CMD ["supervisord", "-c", "/etc/supervisor.conf"]
