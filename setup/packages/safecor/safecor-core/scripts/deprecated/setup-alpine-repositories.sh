#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."
logger -s -t "Safecor/$SCRIPT_NAME" -p user.warn "*** Deprecated ***"


echo *** Deprecated ***
exit 0

. /etc/safecor/constants.sh

echo "$ALPINE_PUBLIC_MAIN_REPOSITORY
$ALPINE_PUBLIC_COMMUNITY_REPOSITORY
$SAPHIR_PUBLIC_REPOSITORY
" > /etc/apk/repositories

apk update