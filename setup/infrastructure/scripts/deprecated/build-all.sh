#!/bin/sh

# Show an error message and quit
error_exit() {
    echo "Error : $1"
    exit 1
}

# List of projects to build
PROJECTS="psec-lib psec-core psec-sys-usb psec-sys-gui psec-gui-base psec-hardening"

# Build a single project
build_project() {
    project=$1

    echo "Starting build of $project..."

    # Sauvegarder le répertoire actuel
    current_dir=$(pwd)

    # Naviguer dans le répertoire du projet
    cd "$project" || error_exit "Failed to enter directory $project"

    # Exécuter abuild checksum
    abuild checksum || error_exit "abuild checksum failed on $project"

    # Exécuter abuild -r pour construire le projet
    abuild -r || error_exit "Failed to build project $project with abuild"

    # Revenir au répertoire précédent
    cd "$current_dir" || error_exit "Unable to change to parent directory"

    echo "$project succesfully built."
}

# Boucle sur chaque projet
for project in $PROJECTS; do
    build_project "$project"
done

echo "All the projects have been successfully built."

ls -l ~/packages/psec/`uname -m`/ 