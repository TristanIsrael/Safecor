#!/bin/sh

PACKAGES="py3-paho-mqtt2 safecor-container-debian safecor-core safecor-demo safecor-demo-gui safecor-diag safecor-gui-base safecor-hardening safecor-lib safecor-splash safecor-sys-gui safecor-sys-usb safecor-syslog safecor-tests safecor-tests-gui"
for pkg in $PACKAGES; do
    ./docker-cmd.sh 'cd /home/builder/src/safecor/setup/packages/safecor/'$pkg' && abuild checksum && abuild clean'
done