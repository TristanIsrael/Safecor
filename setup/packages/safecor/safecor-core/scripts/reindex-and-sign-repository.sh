#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

. /etc/safecor/constants.sh

logger -t "Safecor/$SCRIPT_NAME" -p user.info "Signing local Alpine repository..."

cd $ALPINE_LOCAL_REPOSITORY/`uname -m`
apk index -d ALPINE -o APKINDEX.tar.gz *.apk
abuild-sign -k /.abuild/local.rsa -p /.abuild/local.rsa.pub APKINDEX.tar.gz

logger -t "Safecor/$SCRIPT_NAME" -p user.info "... done"