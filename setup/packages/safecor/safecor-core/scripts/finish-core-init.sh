#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

. /etc/safecor/constants.sh

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Creating the directories..."

mkdir -p /etc/safecor/xen    
mkdir -p /var/log/safecor
chgrp safecor /etc/safecor
chgrp safecor /etc/safecor/xen
chmod 2770 /etc/safecor
chmod 2770 /etc/safecor/xen

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"

/usr/lib/safecor/bin/setup-xen-environment.sh

/usr/bin/python3 /usr/lib/safecor/bin/create-domains.py $ALPINE_LOCAL_REPOSITORY/`uname -m`
