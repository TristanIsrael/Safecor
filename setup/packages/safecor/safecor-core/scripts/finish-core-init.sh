#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."


#if [ -n "$OPENRC_RUNLEVEL" ]
#then
#    echo "Started from initd, ignored"
#else
    . /etc/safecor/constants.sh

    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Creating the directories..."

    mkdir -p /usr/lib/safecor/storage
    mkdir -p /usr/lib/safecor/packages
    mkdir -p /etc/safecor/xen    
    mkdir -p /var/log/safecor
    chgrp safecor /etc/safecor
    chgrp safecor /etc/safecor/xen
    chmod 2770 /etc/safecor
    chmod 2770 /etc/safecor/xen
    
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"

    /usr/lib/safecor/bin/generate-pgp-keys.sh
    /usr/lib/safecor/bin/setup-alpine-repositories.sh
    /usr/lib/safecor/bin/create-local-alpine-repository.sh
    /usr/lib/safecor/bin/setup-xen-environment.sh

    #echo ... Start initd scripts
    #rc-service setup-pci start
    
    /usr/bin/python3 /usr/lib/safecor/bin/create-domains.py $ALPINE_LOCAL_REPOSITORY/`uname -m`

    # Orchestrator will be started on demand
    #rc-service orchestrator start

    #rc-service xen-pci start
    #rc-service attach-pci-devices start    
    #rc-service start-domains start
#fi