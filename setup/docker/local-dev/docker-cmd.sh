#!/bin/sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PRIVATE_KEY="/Volumes/SECURITY/Safecor/abuild/safecor.rsa"
SAFECOR_SOURCE_PATH="/Users/tristanisrael/Documents/Sources/Safecor"
DOCKER_PATH="/usr/local/bin"
IMAGE_NAME="safecor-dev"
DOCKER_NAME="safecor-dev"
STAGE="dev"
LOCAL_ARCH=$(docker info --format '{{.Architecture}}')
EMULATE=0
MOUNT_REPO=""
INTERACTIVE=""

if [ $LOCAL_ARCH != "amd64" ]; then
    echo "Must emulate x86_64 architecture..."
    EMULATE=1
fi

if [ -n "$OVERRIDE_REPOSITORIES" ]; then 
    echo "Override repositories in the container"
    MOUNT_REPO="--mount type=bind,source=$SCRIPT_DIR/repositories,target=/etc/apk/repositories,readonly"
    PIP_REPO="--mount type=bind,source=$SCRIPT_DIR/pip.conf,target=/home/builder/.pip/pip.conf,readonly"
fi

if [ $EMULATE -eq 1 ]; then
    echo "Start emulated Docker"

    if [ "$#" -lt 1 ]; then 
        echo "Starting container with TTY terminal"

        # Run the container
        "$DOCKER_PATH/docker" run \
        -it \
        --rm \
        --platform linux/amd64 \
        $MOUNT_REPO \
        $PIP_REPO \
        --mount type=bind,source=$PRIVATE_KEY,target=/home/builder/.abuild/safecor.rsa,readonly \
        -v "$SAFECOR_SOURCE_PATH:/home/builder/src/safecor" \
        -e STAGE="$STAGE" \
        --name "$DOCKER_NAME" \
        "$IMAGE_NAME" 
    else 
        echo "Starting docker with a command"

        # Run the container
        "$DOCKER_PATH/docker" run \
        --rm \
        --platform linux/amd64 \
        $MOUNT_REPO \
        $PIP_REPO \
        --mount type=bind,source=$PRIVATE_KEY,target=/home/builder/.abuild/safecor.rsa,readonly \
        -v "$SAFECOR_SOURCE_PATH:/home/builder/src/safecor" \
        -e STAGE="$STAGE" \
        --name "$DOCKER_NAME" \
        "$IMAGE_NAME" \
        sh -c "$@"
    fi
else
    echo "Start native Docker"

    if [ "$#" -lt 1 ]; then 
        echo "Starting container with TTY terminal"

        # Run the container
        "$DOCKER_PATH/docker" run \
        --rm \
        -it \
        $MOUNT_REPO \
        $PIP_REPO \
        --mount type=bind,source=$PRIVATE_KEY,target=/home/builder/.abuild/safecor.rsa,readonly \
        -v "$SAFECOR_SOURCE_PATH:/home/builder/src/safecor" \
        -e STAGE="$STAGE" \
        --name "$DOCKER_NAME" \
        "$IMAGE_NAME" 
    else 
        echo "Starting docker with a command"

        # Run the container
        "$DOCKER_PATH/docker" run \
        --rm \
        $MOUNT_REPO \
        $PIP_REPO \
        --mount type=bind,source=$PRIVATE_KEY,target=/home/builder/.abuild/safecor.rsa,readonly \
        -v "$SAFECOR_SOURCE_PATH:/home/builder/src/safecor" \
        -e STAGE="$STAGE" \
        --name "$DOCKER_NAME" \
        "$IMAGE_NAME" \
        sh -c "$@"
    fi
fi
