#!/bin/sh

set -e

logger -s -t "Safecor/core" -p user.info "Setup the XEN environment"

. /etc/safecor/constants.sh

# Setup the replacement script for qemu-system to patch the command
# line sent by XEN
# Setup QEMU proxy for XEN display
# TODO: replace with an alias
if [ ! -L /usr/bin/qemu-system-x86_64 ]; then
    mv /usr/bin/qemu-system-x86_64 /usr/bin/qemu-system-x86_64.real
    ln -s /usr/bin/qemu-system-x86_64.cmd /usr/bin/qemu-system-x86_64
    logger -s -t "Safecor/core" -p user.info "QEMU command line patched"
else
    logger -s -t "Safecor/core" -p user.info "QEMU is already patched"
fi

#CONFIG_REPO=`jq -r '.network.repository' /etc/safecor/topology.json`
#CONFIG_RELEASES=`jq -r '.network.releases' /etc/safecor/topology.json`

# Check whether the Alpine virt ISO image is present
rm -rf /var/lib/xen/boot

if [ -f $ALPINE_VIRT_ISO_LOCAL ]
then 
    logger -s -t "Safecor/core" -p user.info "Alpine virt ISO image is PRESENT"
else
    logger -s -t "Safecor/core" -p user.err "Alpine virt ISO image is MISSING"
    exit 1
fi

if [ -f $ALPINE_LTS_ISO_LOCAL ]
then 
    logger -s -t "Safecor/core" -p user.info "Alpine standard ISO image is PRESENT"
else
    logger -s -t "Safecor/core" -p user.err "Alpine standard ISO image is MISSING"
    exit 1   
fi

logger -s -t "Safecor/core" -p user.info "Successfully setup the XEN environment"