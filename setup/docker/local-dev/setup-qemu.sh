#!/bin/sh

DOCKER_PATH="/usr/local/bin"

LOCAL_ARCH=$(docker info --format '{{.Architecture}}')
EMULATE=0

if [ $LOCAL_ARCH != "amd64" ]; then
    EMULATE=1
fi

if [ $EMULATE -eq 1 ]; then
    echo "Register QEMU image"

    "$DOCKER_PATH/docker" run --rm --privileged multiarch/qemu-user-static --reset -p yes
else 
    echo "No emulation is needed."
fi
