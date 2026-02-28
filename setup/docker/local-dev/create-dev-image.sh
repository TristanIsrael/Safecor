#!/bin/sh

DOCKER_PATH="/usr/local/bin"

"$DOCKER_PATH"/docker build --platform linux/amd64 -t safecor-dev .