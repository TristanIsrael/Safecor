#!/bin/sh

echo "Enable fs-verity for all files of the system"

enable_fsverity() {
    local file="$1"
    fsverity enable "$file"
    if [ $? -gt 0 ];then
        echo "Could not enable fsverity on $file" >&2
    fi
}

find / -type f | while IFS= read -r file; do 
    enable_fsverity "$file"
done
