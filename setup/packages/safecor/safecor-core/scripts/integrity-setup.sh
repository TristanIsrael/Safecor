#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

enable_fsverity() {
    local file="$1"
    fsverity enable "$file"
    if [ $? -gt 0 ];then
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.error "Could not enable fs-verity on $file"
    fi
}

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Enable fs-verity for all files of the system"
find / -type f | while IFS= read -r file; do 
    enable_fsverity "$file"
done
