#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

. /etc/safecor/constants.sh

if grep -q "PANOPTISCAN_CONFIG=nomade" "/proc/cmdline"; then
    echo "*** La configuration est déjà nomadisée. Le dépôt est déjà prêt. ***"
    exit 0
fi

#REPODIR=/var/cache/alpine/`uname -m`
#PAN-127 : Le disque peut être préparé avant ou en RAM, la racine du dépôt est définie dans la variable REPO_ROOT
ALPINE_ARCH_DIR=$ALPINE_LOCAL_REPOSITORY/`uname -m`

mkdir -p $ALPINE_ARCH_DIR
cd $ALPINE_LOCAL_REPOSITORY
ln -s `uname -m` noarch
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Created the local repository dir at $ALPINE_LOCAL_REPOSITORY"

# Construction d'un dépôt local pour les VM domU
# Le dépôt local sera signé avec sa propre clé
# Pour converger avec la configuration nomade il faut
# que les dépôts Alpine et Panoptiscan soient séparés
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Fetch packages..."
cd $ALPINE_ARCH_DIR
apk fetch -R safecor-lib safecor-sys-usb 
# Récupération de dépendances supplémentaires
apk fetch -R libtirpc-conf krb5-conf eudev-openrc udev-init-scripts udev-init-scripts-openrc
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"

/usr/lib/safecor/bin/reindex-and-sign-repository.sh
