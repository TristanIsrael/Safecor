#!/bin/sh

#if [ -n "$OPENRC_RUNLEVEL" ]
#then
#    echo "Started from initd, ignored"
#else
    . /etc/safecor/constants.sh

    mkdir -p /usr/lib/safecor/storage
    mkdir -p /usr/lib/safecor/packages
    mkdir -p /etc/safecor/xen
    mkdir -p /var/log/safecor

    /usr/lib/safecor/bin/generate-pgp-keys.sh
    /usr/lib/safecor/bin/setup-alpine-repositories.sh
    /usr/lib/safecor/bin/create-local-alpine-repository.sh
    /usr/lib/safecor/bin/setup-xen-environment.sh

    echo ... Start initd scripts
    #rc-service setup-pci start

    echo Create XEN Domains
    /usr/bin/python3 /usr/lib/safecor/bin/create-domains.py $ALPINE_LOCAL_REPOSITORY/`uname -m`

    # Orchestrator will be started on demand
    #rc-service orchestrator start

    #rc-service xen-pci start
    #rc-service attach-pci-devices start    
    #rc-service start-domains start
#fi