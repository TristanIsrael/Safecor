#!/bin/sh

show_help() {
    cat <<EOF

Synchronizes a local repository with the official repository.
WARNING: wget must be installed.

Usage: $(basename "$0") [OPTIONS] <repository dir> <arch>

Options:
  -h, --help    Show this help message and exit

Example:
  $(basename "$0") -v
EOF
}

# Handle -h / --help explicitly
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
    exit 0
fi

# Expect exactly two arguments
if [ "$#" -ne 2 ]; then
    echo "Error: missing argument" >&2
    show_help
    exit 1
fi

DIR="$1"

# Validate directory
if [ ! -d "$DIR" ]; then
    echo "Error: '$DIR' is not a directory" >&2
    exit 1
fi


ARCH="$2"

# ---- Main logic ----
echo "Synchronizing official repository with the directory $DIR"
wget -4 --recursive --no-parent -nH --cut-dirs=2 -R "index.html*" -e robots=off --accept "*.apk" -P $DIR https://www.alefbet.net/github/safecor/$ARCH/