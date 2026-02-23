#!/bin/sh

show_help() {
    cat <<EOF

Synchronizes a local directory with the official Safecor ISO images.
WARNING: wget must be installed.

Usage: $(basename "$0") [OPTIONS] <local ISO directory>

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

# Expect exactly one argument
if [ "$#" -ne 1 ]; then
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
echo "Synchronizing official ISO images with the directory $DIR"
wget -4 --recursive --no-parent -nH --cut-dirs=3 -R "index.html*" -e robots=off --accept "*.iso" -P $DIR https://www.alefbet.net/github/safecor/iso/