#!/bin/sh

######
# This script creates a local storage as a tmpfs mount point
# and hardens it. The storage's size will be half of the available
# memory in Dom0.
#
# Arguments
#   no argument
#
# This script must be ran as root

echo "Creating a memory local storage"

# Fail on error
set -e

mount -t tmpfs -o noexec,nosuid,nodev tmpfs /usr/lib/safecor/storage
