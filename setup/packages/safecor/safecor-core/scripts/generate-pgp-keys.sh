#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

rm -rf /$USER/.abuild

logger -t "Safecor/$SCRIPT_NAME" -p user.info "Generating the abuild key-pair..."
abuild-keygen -nq
ln -s `ls /$USER/.abuild/*-*.rsa.pub` /$USER/.abuild/local.rsa.pub
ln -s `ls /$USER/.abuild/*-*.rsa` /$USER/.abuild/local.rsa

logger -t "Safecor/$SCRIPT_NAME" -p user.info "Copying abuild keys..."
cp `ls /$USER/.abuild/*-*.rsa.pub` /etc/apk/keys/local.rsa.pub

logger -t "Safecor/$SCRIPT_NAME" -p user.info "... finished"
