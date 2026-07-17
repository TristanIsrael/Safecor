#!/bin/sh

######
# This script creates a local storage as an encrypted file on the 
# local hard drive if any.
#
# Arguments
#   $1 - the index of the disk to use (starting at 1)
#   $2 - the storage size in MB
#
# This script must be ran as root

logger -t "Safecor/core" -p user.notice "Creating an encrypted local storage on the local physical disk"

# Fail on error
set -e

# 1st step: verify that there is a physical drive
disks=$(lsblk -d -n -o NAME,TYPE | awk '$2=="disk"{print $1}')

if [ -z "$disks" ]; then
    logger -t "Safecor/core" -p user.warn "No physical disk detected. Aborting."
    exit 1
fi

# Select the nth disk
disk_idx=1
if [ "$1" != "" ]; then
    disk_idx=$1
fi 

logger -t "Safecor/core" -p user.info "Using the disk at index $disk_idx"

dev=$(printf '%s\n' $disks | awk "NR==$disk_idx")

if [ -z "$dev" ]; then
    echo "There is no disk at index $disk_idx"
    return 2
fi 

logger -t "Safecor/core" -p user.info "Device: /dev/$dev"

# 2d step: partition and format the physical drive
wipefs -a "/dev/$dev"
echo ",,L,*" | sfdisk "/dev/$dev"
if [ $? -ne 0 ]; then
    logger -t "Safecor/core" -p user.warn "There has been an error while partitioning the disk"
    return 3
fi

mkfs.ext4 -F -L Safecor "/dev/$dev"
if [ $? -ne 0 ]; then
    logger -t "Safecor/core" -p user.warn "There has been an error while formatting the disk"
    return 3
fi

mkdir -p /media/$dev
mount -o noexec,nosuid,nodev LABEL=Safecor /media/$dev
if [ $? -ne 0 ]; then
    logger -t "Safecor/core" -p user.warn "Could not mount the disk"
    return 4
fi

# 3d step: create a key pair for the encryption
mkdir -p /dev/shm/keys
head -c 64 /dev/urandom > /dev/shm/keys/local_storage

# 4th step: create a ciphered file
storage_size=1024
if [ "$2" != "" ]; then
    storage_size=$2
fi

# If the storage size is set to -1 we use 95% of the disk capacity
if [ "$2" -eq -1 ]; then
    logger -t "Safecor/core" -p user.info "The storage file will use the whole disk"
    disk_size=$(blockdev --getsize64 /dev/$dev)
    storage_size_bytes=$disk_size #$((disk_size * 95 / 100))
else
    logger -t "Safecor/core" -p user.info "Create a storage file of size $storage_size MB"
    storage_size_bytes=$((storage_size * 1024 * 1024))
fi 

truncate -s $storage_size_bytes /media/$dev/storage.img
# To avoid the cost of the PBKDF which is unnecessary because we generate a random key we use specific parameters
cryptsetup luksFormat --type luks2 --pbkdf pbkdf2 --pbkdf-force-iterations 1000 --batch-mode /media/$dev/storage.img --key-file /dev/shm/keys/local_storage
cryptsetup luksOpen /media/$dev/storage.img storage --key-file /dev/shm/keys/local_storage
losetup /dev/loop1 /media/$dev/storage.img
mkfs.ext4 /dev/mapper/storage

# 5th step: mount the ciphered file
mkdir -p /usr/lib/safecor/storage
mount -o noexec,nosuid,nodev /dev/mapper/storage /usr/lib/safecor/storage

# Last step: set the permissions on the files
chown root:safecor /media/$dev/storage.img
chmod 660 /media/$dev/storage.img
chown root:safecor /media/$dev
chmod 750 /media/$dev
chown svc-safecor-controller:safecor /usr/lib/safecor/storage
chmod 2770 /usr/lib/safecor/storage

logger -t "Safecor/core" -p user.notice "The local storage has been successfully created with a size of $storage_size_bytes bytes"