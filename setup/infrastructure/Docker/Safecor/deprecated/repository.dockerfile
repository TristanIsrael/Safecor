FROM alpine:latest

ARG ALPINE_VERSION
ARG LOCAL_REPOSITORY_PATH
VOLUME [ "${LOCAL_REPOSITORY_PATH}:/mnt/repository,ro" ]

RUN echo "${LOCAL_REPOSITORY_PATH}"

RUN echo "/mnt/repository/alpine/v${ALPINE_VERSION}/main" > /etc/apk/repositories
RUN echo "/mnt/repository/alpine/v${ALPINE_VERSION}/community" >> /etc/apk/repositories

RUN apk add --no-cache nginx
