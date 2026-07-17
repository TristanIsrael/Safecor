#!/bin/sh

# Handles the block devices detected by udev
#
# A block device with a filesystem can be:
# - a disk (DEVTYPE=disk) without partition (ID_FS_USAGE=filesystem)
# - a partition (DEVTYPE=partition, ID_FS_USAGE=filesystem)
#
# This script handles both cases

unique_file()
{
    # We create a unique filename for the mount point
    file="$1"

    if [ ! -e "$file" ]; then
        echo "$file"
        return
    fi

    n=1

    while [ -e "${file}.${n}" ]; do
        n=$((n + 1))
    done

    echo "${file}.${n}"
}

if [ -z "$ID_FS_USAGE" ]; then
    # Not a filesystem
    exit
fi 

if [ "$ID_FS_USAGE" != "filesystem" ]; then 
    # Not a filesystem
    exit
fi

LABEL=$(printf "%b" "$ID_FS_LABEL_ENC")
# If the label is empty call it "NONAME"
if [ -z "$LABEL" ]; then
    LABEL="NONAME"
fi

# Replace empty spaces with underscores
LABEL=$(echo "$LABEL" | sed 's/ /_/g')

# Make the mount point unique
LABEL=$(unique_file $LABEL)

FS=$ID_FS_TYPE
MOUNT_POINT="/media/usb/$LABEL"
DEVICE=$DEVNAME
SCRIPTS_PATH=/usr/lib/safecor/bin
LOG_FILENAME=/var/log/safecor/udev.log

mkdir -p `dirname $LOG_FILENAME`

#echo "Action : $ACTION" >> $LOG_FILENAME

if [ "$ACTION" == "add" ]
then
	logger -t "Safecor/sys-usb/mdev-usb-storage" -p user.debug "Mounting disk $LABEL with filesystem $FS in $MOUNT_POINT"
	mkdir -p "$MOUNT_POINT"	
    mount -o uid=1000,gid=2000,umask=007,noexec,nosuid,nodev $DEVICE "$MOUNT_POINT"
    chown svc-sys-usb-controller:safecor "$MOUNT_POINT"
    chmod 770 "$MOUNT_POINT"    

    if [ $? -eq 0 ]
    then
        logger -t "Safecor/sys-usb/mdev-usb-storage" -p user.notice "Successfully mounted $MOUNT_POINT"
    fi
fi

if [ "$ACTION" == "remove" ]
then
	logger -t "Safecor/sys-usb/mdev-usb-storage" -p user.info "Umounting $MOUNT_POINT"

    if [ $? -eq 0 ]
    then
        logger -t "Safecor/sys-usb/mdev-usb-storage" -p user.notice "Successfully unmounted $MOUNT_POINT"
    fi

	rmdir "$MOUNT_POINT"
fi

if [ "$ACTION" == "change" ] 
then
    if [ -n "$FS" ]
    then
        logger -t "Safecor/sys-usb/mdev-usb-storage" -p user.notice "Changed state for $MOUNT_POINT with FS $FS and label $LABEL"
        logger -t "Safecor/sys-usb/mdev-usb-storage" -p user.info "Mounting disk $LABEL with filesystem $FS in $MOUNT_POINT"
        
        mkdir -p "$MOUNT_POINT" 
        mount -o uid=1000,gid=2000,umask=007,noexec,nosuid,nodev $DEVICE "$MOUNT_POINT"     
        chown svc-sys-usb-controller:safecor "$MOUNT_POINT"
        chmod 770 "$MOUNT_POINT"        

        if [ $? -eq 0 ]
        then
            logger -t "Safecor/sys-usb/mdev-usb-storage" -p user.info "Successfully mounted $MOUNT_POINT"
        fi
    fi
fi
