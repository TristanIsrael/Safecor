#!/bin/sh

source `dirname "$0"`/constants.sh

cd $1
scp -r $REMOTE_USER@$REMOTE_IP:$REMOTE_PACKAGES_DIR $REMOTE_USER@$PUBLIC_UNC:$PUBLIC_PACKAGES_DIR/psec/
cd -

echo Copîe terminée