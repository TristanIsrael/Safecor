#!/bin/sh

set -e

logger -s -t "Safecor/core" -p user.notice "Create the keys for the repository..."

rm -rf /$USER/.abuild

abuild-keygen -nq
ln -s `ls /$USER/.abuild/*-*.rsa.pub` /$USER/.abuild/local.rsa.pub
ln -s `ls /$USER/.abuild/*-*.rsa` /$USER/.abuild/local.rsa
logger -s -t "Safecor/core" -p user.info "The abuild key-pair has been generated"

cp `ls /$USER/.abuild/*-*.rsa.pub` /etc/apk/keys/local.rsa.pub

logger -s -t "Safecor/core" -p user.info "Successfully created the keys for the repository"
