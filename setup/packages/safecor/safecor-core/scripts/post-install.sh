#!/bin/sh

/usr/lib/safecor/bin/finish-core-init.sh

logger -s -t "Safecor/core" -p user.info "Safecor's core has been initialized successfully"

rc-service orchestrator start

echo ''
echo ''
echo ''
echo '    .d8888b.            .d888                                   '
echo '    d88P  Y88b          d88P"                                   '
echo '    Y88b.               888                                     '
echo '     "Y888b.    8888b.  888888 .d88b.   .d8888b .d88b.  888d888 '
echo '        "Y88b.     "88b 888   d8P  Y8b d88P"   d88""88b 888P"   '
echo '          "888 .d888888 888   88888888 888     888  888 888     '
echo '    Y88b  d88P 888  888 888   Y8b.     Y88b.   Y88..88P 888     '
echo '     "Y8888P"  "Y888888 888    "Y8888   "Y8888P "Y88P"  888     '
echo ''
echo ''
echo '                     --| INSTALLATION DONE |--'
echo ''
echo ''