#!/bin/sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PRIVATE_KEY="/Users/tristanisrael/Documents/Sources/crypto/safecor.rsa"
SAFECOR_SOURCE_PATH="/Users/tristanisrael/Documents/Sources/Safecor"
DOCKER_PATH="/usr/local/bin"
IMAGE_NAME="alpine-dev"
DOCKER_NAME="alpine-dev"
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
    MOUNT_REPO="--mount type=bind,source="$SCRIPT_DIR/repositories",target=/etc/apk/repositories,readonly"
fi 

if [ "$#" -eq 0 ]; then 
    echo "Starting container with TTY terminal"
    INTERACTIVE="-it"
else 
    echo "Starting docker with a command"
fi

if [ $EMULATE -eq 1 ]; then
    echo "Start emulated Docker"

    # Run the container
    "$DOCKER_PATH/docker" run \
    $INTERACTIVE \
    --rm \
    --platform linux/amd64 \
    --mount type=bind,source="$PRIVATE_KEY",target=/home/builder/.abuild/safecor.rsa,readonly \
    $MOUNT_REPO \
    -v "$SAFECOR_SOURCE_PATH:/home/builder/src/safecor" \
    -e STAGE="$STAGE" \
    --name "$DOCKER_NAME" \
    "$IMAGE_NAME" \
    sh -c "$@"
else
    echo "Start native Docker"

    "$DOCKER_PATH/docker" run \
    $INTERACTIVE \
    --rm \
    --mount type=bind,source="$PRIVATE_KEY",target=/home/builder/.abuild/safecor.rsa,readonly \
    $MOUNT_REPO \
    -v "$PRIVATE_KEY:/home/builder/.abuild/safecor.rsa:ro" \
    -e STAGE="$STAGE" \
    --name "$DOCKER_NAME" \    
    "$IMAGE_NAME" \
    sh -c "$@"
fi

