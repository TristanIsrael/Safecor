#!/bin/sh

logger -s -t "Safecor/core" -p user.notice "The Domain $1 will be rebooted"
/usr/sbin/xl reboot $1
