#!/bin/sh

set -e

SWAP_FILEPATH=$1
SWAP_SIZE=$2

logger -t "Safecor/core" -p user.info "Create swap diskfile of size $2 in file $1"

# Allocate the file
/usr/bin/fallocate -l $SWAP_SIZE $SWAP_FILEPATH

# Partition the Swap diskfile
printf 'n\np\n1\n\n\nt\n82\nw\n' | fdisk $SWAP_FILEPATH

logger -t "Safecor/core" -p user.info "The swap disk file has been successfully created"