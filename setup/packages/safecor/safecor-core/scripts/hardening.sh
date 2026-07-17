#!/bin/sh

set -e

if [ "$1" == "DEBUG" ]; then
    logger -t "Safecor/core" -p user.notice "Apply hardening on the core in DEBUG mode"
else 
    logger -t "Safecor/core" -p user.notice "Apply hardening on the core"

    # Unload network drivers
    modprobe -r af_packet 
    modprobe -r virtio_net 
    modprobe -r net_failover

    # Disable module loading after this point
    #sysctl -w kernel.modules_disabled=1

    # Disable ptrace completely
    sysctl -w kernel.yama.ptrace_scope=3
fi

logger -t "Safecor/core" -p user.notice "Successfully hardened the core"