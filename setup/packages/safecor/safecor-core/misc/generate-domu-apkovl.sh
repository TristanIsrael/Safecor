#!/bin/sh

if [ "$#" -ne 1 ]; then
    echo "Missing path of the domu template directory"
    exit 1
fi

tar cvzf domu.apkovl.tar.gz.tmpl -C $1/ --exclude ".DS_Store" .