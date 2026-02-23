#!/bin/sh

# Vérifier si le nombre d'arguments n'est pas égal à 1
if [ $# -ne 1 ]; then
    echo "Erreur : Il manque le chemin du dépôt local."
    echo "Usage : $0 <argument>"
    exit 1
fi

cd $1
scp -P222 *.apk APKINDEX.tar.gz tristan@www.alefbet.net:~/Safecor/bin
cd -

echo Copîe terminée