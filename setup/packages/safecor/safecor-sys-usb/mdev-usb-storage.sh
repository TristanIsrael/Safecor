#!/bin/sh

LABEL=$(printf "%b" "$ID_FS_LABEL_ENC")
# Si le label est vide, utiliser "NONAME"
if [ -z "$LABEL" ]; then
    LABEL="NONAME"
fi

# Remplacer les espaces par des underscores
LABEL=$(echo "$LABEL" | sed 's/ /_/g')

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
