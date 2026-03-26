FROM jpillora/dnsmasq

ARG REPOSITORY_SERVER_IP 
ARG ALPINE_VERSION

VOLUME [ "/Users/tristanisrael/Documents/Depots:/mnt/repository" ]

RUN echo "/mnt/repository/latest/main" > /etc/apk/repositories
RUN echo "/mnt/repository/latest/community" >> /etc/apk/repositories

RUN apk add --no-cache gettext