#!/bin/sh

set -e

logger -s -t "Safecor/core" -p user.notice "Finish the core initialization..."

. /etc/safecor/constants.sh

mkdir -p /etc/safecor/xen    
mkdir -p /var/log/safecor
chgrp safecor /etc/safecor
chgrp safecor /etc/safecor/xen
chmod 2770 /etc/safecor
chmod 2770 /etc/safecor/xen

logger -t "Safecor/core" -p user.info "The directories have been created"

/usr/lib/safecor/bin/setup-xen-environment.sh

/usr/bin/python3 /usr/lib/safecor/bin/create-domains.py $ALPINE_LOCAL_REPOSITORY/`uname -m`
