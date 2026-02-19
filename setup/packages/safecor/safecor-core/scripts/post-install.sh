#!/bin/sh

/usr/lib/safecor/bin/finish-core-init.sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting the orchestrator service"

rc-service orchestrator start

#rc-service start-domains start
#rc-service connect-to-gui start


echo "***************************************"
echo "******          Safecor          ******"
echo "******          -------          ******"
echo "******                           ******"
echo "******   Installation finished   ******"
echo "******                           ******"
echo "***************************************"