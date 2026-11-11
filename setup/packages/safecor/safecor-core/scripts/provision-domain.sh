#!/bin/sh
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md


SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

. /etc/safecor/constants.sh

export APKOVL_TEMPLATE="/usr/lib/safecor/system/domu.apkovl.tar.gz"
export LOCAL_PGP_PUBKEY="/etc/apk/keys/local.rsa.pub"

## Local variables
export WORKDIR="/usr/lib/safecor/tmp/domu.tmp"

if [ $# -lt 4 ]; then
  logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "Mandatory arguments missing..."

  echo "Mandatory arguments missing."
  echo "$0 [Domain name] [Main package] [Alpine branch (virt|lts)] [blacklist.conf file path]"
  exit 1
fi

DOMAIN=$1
MAIN_PACKAGE=$2
ALPINE_BRANCH=$3
ALPINE_BRANCH=${ALPINE_BRANCH:-virt}
BLACKLIST_CONF=$4
CONFIG_IMG="$WORKDIR/$DOMAIN-config.img"

# Vérifier la valeur de $ALPINE_BRANCH et définir $BOOTISO_FILENAME en conséquence
case "$ALPINE_BRANCH" in
  lts)
    export ALPINE_ISO_LOCAL=$ALPINE_LTS_ISO_LOCAL
    ;;
  virt)
    export ALPINE_ISO_LOCAL=$ALPINE_VIRT_ISO_LOCAL
    ;;
  *)
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "Unknown value for ALPINE_BRANCH : $ALPINE_BRANCH"

    exit 1
    ;;
esac

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Create new XEN User Domain $DOMAIN"
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "  main package : $MAIN_PACKAGE"
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "  Alpine branch : $ALPINE_BRANCH"
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "  Kernel modules blacklist : $BLACKLIST_CONF"

rm -rf /mnt/config_img
mkdir -p /mnt/config_img

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Prepare"
rm -rf $WORKDIR 
mkdir -p $WORKDIR/apkovl

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Uncompress APK overlay template"
tar xzf $APKOVL_TEMPLATE -C $WORKDIR/apkovl

cd $WORKDIR/apkovl

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Configure main package"
echo "
safecor-lib
$MAIN_PACKAGE" >> $WORKDIR/apkovl/etc/apk/world

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Configure hostname"
echo "$DOMAIN" > $WORKDIR/apkovl/etc/hostname

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Copy local PGP key"
cp $LOCAL_PGP_PUBKEY $WORKDIR/apkovl/etc/apk/keys

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Set permissions"
chmod +x etc/init.d/*
chown 0:0 etc/init.d/*

if [ -e "$BLACKLIST_CONF" ]; then
    mkdir -p etc/modprobe.d
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Patch modules blacklist"
    cat $BLACKLIST_CONF >> etc/modprobe.d/blacklist.conf
fi

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Create new APK overlay"
cd $WORKDIR/apkovl
tar czf $WORKDIR/$DOMAIN.apkovl.tar.gz .

#logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Create new ISO"
#xorriso -as mkisofs -r -V "BOOT" -cache-inodes -J -l -b boot/syslinux/isolinux.bin -c boot/syslinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -o /usr/lib/safecor/tmp/$BOOTISO_FILENAME $WORKDIR/iso
#mv /usr/lib/safecor/tmp/$BOOTISO_FILENAME /usr/lib/safecor/system/

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Create config disk for $DOMAIN"
rm -rf "$CONFIG_IMG"
dd if=/dev/zero of="$CONFIG_IMG" bs=1M count=1
mkfs.ext4 "$CONFIG_IMG"

mount -o loop $CONFIG_IMG /mnt/config_img
cp $WORKDIR/$DOMAIN.apkovl.tar.gz /mnt/config_img
umount /mnt/config_img

mv "$CONFIG_IMG" "/usr/lib/safecor/system"

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Clean"
rm -rf /mnt/bootiso
rm -rf $WORKDIR
