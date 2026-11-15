#!/bin/sh

NEW_ARGS=$(echo "$@" | sed \
    -e 's/-vnc none//g' \
    -e 's/-machine xenfv/-machine xenfv-4.2/g')
#echo $NEW_ARGS > /tmp/debug.cmd
exec /usr/bin/qemu-system-x86_64.real $NEW_ARGS