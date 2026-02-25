#!/bin/sh
# Args: [mount point] [FS type]

if [ $# -ne 4 ]; then
    echo "Usage: $0 <mount_point> <filename_prefix> <dir_levels> <qty_of_files>"
    exit 1
fi

# Target folder
TARGET_DIR="$1"
PREFIX="$2"
LEVELS="$3"
NUM_FILES="$4"

if [ ! -d "$TARGET_DIR" ]; then 
    echo "Error: the directory '$TARGET_DIR' does not exist"
    exit 1
fi

generate_random_path() {
    local base="$TARGET_DIR"
    local max_levels="$LEVELS"
    local levels=$(( RANDOM % max_levels + 1 ))  # entre 1 et max_levels
    local path="$base"

    for ((i=0; i<levels; i++)); do
        dir="dir_$((RANDOM % 1000))"
        path="$path/$dir"
    done

    echo "$path"
}

for ((i=0; i<NUM_FILES; i++)); do
    DIR_PATH=$(generate_random_path "$TARGET_DIR" "$LEVELS")
    mkdir -p "$DIR_PATH"

    FILE="$DIR_PATH/${PREFIX}_${i}.bin"

    # Taille aléatoire entre 1 Ko et 100 Mo
    SIZE_KB=$(( RANDOM % 102400 + 1 ))

    echo "Creating $FILE of size ${SIZE_KB} KB ..."
    dd if=/dev/urandom of="$FILE" bs=1K count=$SIZE_KB status=none

    if [ $? -ne 0 ]; then
        echo "Disk full or error reached."
        exit 0
    fi
done

echo "Finished creating files in $TARGET_DIR"
