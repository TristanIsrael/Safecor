#!/bin/sh

/usr/sbin/xl list | grep "^sys-gui" | awk '{print $2}'

return 0