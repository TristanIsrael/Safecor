#!/bin/sh

set -e

logger -s -t "Safecor/core" -p user.info "Start the provisioning of the Domain $1"

. /etc/safecor/constants.sh

export APKOVL_TEMPLATE="/usr/lib/safecor/system/domu.apkovl.tar.gz"
export LOCAL_PGP_PUBKEY="/etc/apk/keys/local.rsa.pub"

## Local variables
export WORKDIR="/usr/lib/safecor/tmp/domu.tmp"

if [ $# -lt 4 ]; then
  logger -s -t "Safecor/core" -p user.err "Mandatory arguments missing..."

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
    logger -s -t "Safecor/core" -p user.err "Unknown value for ALPINE_BRANCH: $ALPINE_BRANCH"

    exit 1
    ;;
esac

logger -s -t "Safecor/core" -p user.info "Create new XEN User Domain $DOMAIN"
logger -s -t "Safecor/core" -p user.info "  main package : $MAIN_PACKAGE"
logger -s -t "Safecor/core" -p user.info "  Alpine branch : $ALPINE_BRANCH"
logger -s -t "Safecor/core" -p user.info "  Kernel modules blacklist : $BLACKLIST_CONF"

# Prepare the directories
rm -rf /mnt/config_img
mkdir -p /mnt/config_img

rm -rf $WORKDIR 
mkdir -p $WORKDIR/apkovl

# Uncompress the overlay template
tar xzf $APKOVL_TEMPLATE -C $WORKDIR/apkovl

cd $WORKDIR/apkovl

# Create the APK world file
echo "
safecor-lib
$MAIN_PACKAGE" >> $WORKDIR/apkovl/etc/apk/world

# Configure the hostname
echo "$DOMAIN" > $WORKDIR/apkovl/etc/hostname

# Copy the local repository key
cp $LOCAL_PGP_PUBKEY $WORKDIR/apkovl/etc/apk/keys

# Set permissions
chmod +x etc/init.d/*
chown 0:0 etc/init.d/*

if [ -e "$BLACKLIST_CONF" ]; then
    mkdir -p etc/modprobe.d
    # Patch modules blacklist if needed
    cat $BLACKLIST_CONF >> etc/modprobe.d/blacklist.conf
fi

# Create the new APK overlay
cd $WORKDIR/apkovl
tar czf $WORKDIR/$DOMAIN.apkovl.tar.gz .
logger -s -t "Safecor/core" -p user.info "The APK overlay file has been successfully created"

rm -rf "$CONFIG_IMG"
dd if=/dev/zero of="$CONFIG_IMG" bs=1M count=1
mkfs.ext4 "$CONFIG_IMG"

mount -o loop $CONFIG_IMG /mnt/config_img
cp $WORKDIR/$DOMAIN.apkovl.tar.gz /mnt/config_img
umount /mnt/config_img
logger -s -t "Safecor/core" -p user.info "The configuration disk has been successfully created"

mv "$CONFIG_IMG" "/usr/lib/safecor/system"

# Clean
rm -rf /mnt/bootiso
rm -rf $WORKDIR

logger -s -t "Safecor/core" -p user.info "Successfully provisioned the Domain $DOMAIN"