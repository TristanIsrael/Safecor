#!/bin/sh

# This script synchronizes the local source repository with an external storage
# Usage: ./script.sh <local_repository> <remote_repository> <in_out>

if [ $# -ne 3 ]; then
    echo "Missing arguments"
    echo "Usage: $0 <local_repository> <remote_repository> <in_out>"
    echo "    Example: $0 source_path /Volumes/USB/Sources/ out"
    echo "    If using IN mode the remote will be synchronized TO the local"
    echo "    If using OUT mode the local will be synchronized TO the remote"
    exit 1
fi

if [ "$3" != "out" ] && [ "$3" != "OUT" ] && [ "$3" != "in" ] && [ "$3" != "IN" ]; then
    echo "The value $3 is not recognized."
    echo "Possible values are in, out, IN, OUT"
    exit 1
fi

if [ "$3" == "out" ] || [ "$3" == "OUT" ]; then 
    echo "Synchronize to the storage"
    rsync -avz --progress --exclude ".git*" --exclude ".DS_Store" --exclude "__pycache__" --exclude ".venv" --exclude "venv.nosync" --delete-excluded --delete-before $1 $2
else
    echo "Synchronize from the storage"
    rsync -avz --progress --exclude ".git*" --exclude ".DS_Store" --exclude "__pycache__" --exclude ".venv" --exclude "venv.nosync" --delete-excluded --delete-before $2 $1
fi

echo "Synchronization finished"
