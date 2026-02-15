build_xen() {
    # XEN section
	apk fetch --root "$APKROOT" --stdout xen-hypervisor | tar -C "$DESTDIR" -xz boot
}

build_splash() {
    # Splash section 
    local file="$1"
    msg "Handling splash file $file"

    local ext="${file##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    if [ ! -f "$file" ]; then
        msg "The splash file '$file' does not exist"
        return 1
    fi

    if [ "$ext" != "ppm" ]; then
        # Convert to PPM
        local out="${file%.*}.ppm"
        msg "Convert splash to PPM format"
        magick convert "$file" "$out"
        file=$out
    fi

    msg "Adding splash image $file to ISO at ${DESTDIR}"
    cp $file ${DESTDIR}/fbsplash.ppm    

    return $?
}

section_xen() {
    # XEN section
	[ -n "${xen_params+set}" ] || return 0
	build_section xen $ARCH $(apk fetch --root "$APKROOT" --simulate xen-hypervisor | checksum)
}

section_splash() {
    # Splash section
    local _splash=""

    for file in splash.ppm splash.png; do
        [ -f "$file" ] && { msg "Splash file found: $file"; _splash=$file break; }
    done

    if [ ! -f "$PWD/$_splash" ]; then 
        msg "Could not open $_splash in $PWD"
        return 0 # Fail silently
    fi

    build_section splash "$PWD/$_splash"
}

profile_safecor() {
    profile_standard

    profile_abbrev="safecor"
    title="Safecor"
    desc="ISO image for Safecor apps"
    arch="x86_64"
		
    kernel_cmdline="$kernel_cmdline console=none loglevel=0"
    syslinux_serial=""
    kernel_addons=""
    kernel_flavors="lts"
    xen_params="quiet console=none loglevel=0"
    apks="$apks rng-tools xen xen-hypervisor syslinux"
    arch="x86_64"
}