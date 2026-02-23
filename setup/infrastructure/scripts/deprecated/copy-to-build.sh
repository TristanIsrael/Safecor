#!/bin/bash

source `dirname "$0"`/constants.sh

echo Is the directory \"$PWD\" the sources root directory?
PS3='> '
LIST=("[y]es" "[n]o")
select CHOICE in "${LIST[@]}"; do
    case $REPLY in
        1|y)
        echo Taper : rsync -a $PWD/ $REMOTE_USER@$REMOTE_IP:$REMOTE_SRC_DIR/psec
        break
        ;;
        2|n)
        echo Cancelled
        break
        ;;
    esac
done
