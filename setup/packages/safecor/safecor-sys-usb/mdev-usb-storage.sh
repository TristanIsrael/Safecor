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
	echo "Mouting disk $LABEL with filesystem $FS in $MOUNT_POINT" >> $LOG_FILENAME
	echo mount $DEVICE "$MOUNT_POINT" >> $LOG_FILENAME >> $LOG_FILENAME
	mkdir -p "$MOUNT_POINT"	
    mount -o uid=1000,gid=1000,umask=007 $DEVICE "$MOUNT_POINT" >> $LOG_FILENAME 2>&1
    chown svc-sys-usb-controller:safecor "$MOUNT_POINT"
    chmod 770 "$MOUNT_POINT"    

    if [ $? -eq 0 ]
    then
        echo "... Success" >> $LOG_FILENAME
    fi
fi

if [ "$ACTION" == "remove" ]
then
	echo "Umounting $MOUNT_POINT" >> $LOG_FILENAME >> $LOG_FILENAME
	umount "$MOUNT_POINT" >> $LOG_FILENAME 2>&1

    if [ $? -eq 0 ]
    then
        echo "... Success" >> $LOG_FILENAME
    fi

	rmdir "$MOUNT_POINT"
fi

if [ "$ACTION" == "change" ] 
then
    if [ -n "$FS" ]
    then
        echo "Change state for $MOUNT_POINT with FS $FS and label $LABEL" >> $LOG_FILENAME >> $LOG_FILENAME

        echo "Mouting disk $LABEL with filesystem $FS in $MOUNT_POINT" >> $LOG_FILENAME
        echo mount $DEVICE $MOUNT_POINT >> $LOG_FILENAME >> $LOG_FILENAME
        mkdir -p "$MOUNT_POINT" 
        mount -o uid=1000,gid=1000,umask=007 $DEVICE "$MOUNT_POINT" >> $LOG_FILENAME 2>&1       
        chown svc-sys-usb-controller:safecor "$MOUNT_POINT"
        chmod 770 "$MOUNT_POINT"        

        if [ $? -eq 0 ]
        then
            echo "... Success" >> $LOG_FILENAME
        fi
    fi
fi
