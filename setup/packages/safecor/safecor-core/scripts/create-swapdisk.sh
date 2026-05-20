#!/bin/sh

SWAP_FILEPATH=$1
SWAP_SIZE=$2

echo Create swap diskfile of size $2 in file $1

echo Create the Swap diskfile
/usr/bin/fallocate -l $SWAP_SIZE $SWAP_FILEPATH

echo Partition the Swap diskfile
printf 'n\np\n1\n\n\nt\n82\nw\n' | fdisk $SWAP_FILEPATH
