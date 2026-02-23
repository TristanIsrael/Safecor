#!/bin/sh

source `dirname "$0"`/constants.sh

# Vérifier si le nombre d'arguments n'est pas égal à 1
if [ $# -ne 1 ]; then
    echo "Erreur : Il manque le chemin du dépôt local."
    echo "Usage : $0 <argument>"
    exit 1
fi

cd $1
scp -r $REMOTE_USER@$REMOTE_IP:$REMOTE_PACKAGES_DIR .
cd -

echo Copîe terminée