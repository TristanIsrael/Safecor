#!/bin/sh

logger -s -t "Safecor/core" -p user.notice "Setup the integrity monitoring"

enable_fsverity() {
    local file="$1"
    fsverity enable "$file"
    if [ $? -gt 0 ];then
        logger -s -t "Safecor/core" -p user.error "Could not enable fs-verity on $file"
    fi
}

logger -s -t "Safecor/core" -p user.info "Enable fs-verity for all files of the system"
find / -type f | while IFS= read -r file; do 
    enable_fsverity "$file"
done
