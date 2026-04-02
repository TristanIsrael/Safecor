#!/bin/sh

DOCKER_PATH="/usr/local/bin"

"$DOCKER_PATH"/docker build -f Dockerfile-offline --platform linux/amd64 -t safecor-dev .