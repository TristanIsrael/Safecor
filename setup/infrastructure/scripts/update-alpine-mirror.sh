#!/bin/sh

if [ "$#" -ne 2 ]; then
    echo "Missing arguments:"
    echo "$0 [x86_64, armv7, aarch64] [version]"
    exit 1
fi

MIRROR_UNC="mirrors.ircam.fr"
MIRROR_ROOT="pub"

REPO_MAIN_ROOT="rsync://$MIRROR_UNC/$MIRROR_ROOT/alpine/v$2/main"
REPO_COMMUNITY_ROOT="rsync://$MIRROR_UNC/$MIRROR_ROOT/alpine/v$2/community"

REPO_MAIN_URL="$REPO_MAIN_ROOT/$1"
REPO_COMMUNITY_URL="$REPO_COMMUNITY_ROOT/$1"

echo "Downloading Alpine packages version $2 for $1"

mkdir -p alpine/v$2/community/$1
echo "URL $REPO_COMMUNITY_URL"
rsync -avz --delete $REPO_COMMUNITY_URL/ alpine/v$2/community/$1/

mkdir -p alpine/v$2/main/$1
echo "URL $REPO_MAIN_URL"
rsync -avz --delete $REPO_MAIN_URL/ alpine/v$2/main/$1/

echo "Update finished"