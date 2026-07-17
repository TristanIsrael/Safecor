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
		
    kernel_cmdline="$kernel_cmdline console=null loglevel=0 autodetect_serial=no kernel.dmesg_restrict=1 kernel.kptr_restrict=2 kernel.pid_max=65535 kernel.perf_cpu_time_max_percent=1 kernel.perf_event_max_sample_rate=1 kernel.perf_event_paranoid=2 kernel.randomize_va_space=2 kernel.sysrq=0 kernel.unprivileged_bpf_disabled=1 kernel.panic_on_oops=1 l1tf=full,force page_poison=on pti=on slab_nomerge=yes slub_debug=FZP spec_store_bypass_disable=seccomp spectre_v2=on mds=full,nosmt mce=0 page_alloc.shuffle=1 rng_core.default_quality=500 modules=sd-mod,usb-storage,ext4,nvme quiet rootfstype=ext4 ipv6.disable=1 apparmor=1 security=apparmor"
    syslinux_serial=""
    kernel_addons=""
    kernel_flavors="lts"
    xen_params="quiet console=null loglevel=0 no-real-mode edd=off dom0_mem=512M,max:1024M dom0_max_vcpus=2 dom0_vcpus_pin=true kernel.dmesg_restrict=1 kernel.kptr_restrict=2 kernel.pid_max=65535 kernel.perf_cpu_time_max_percent=1 kernel.perf_event_max_sample_rate=1 kernel.perf_event_paranoid=2 kernel.randomize_va_space=2 kernel.sysrq=0 kernel.unprivileged_bpf_disabled=1 kernel.panic_on_oops=1 l1tf=full,force page_poison=on pti=on slab_nomerge=yes slub_debug=FZP spec_store_bypass_disable=seccomp spectre_v2=on mds=full,nosmt mce=0 page_alloc.shuffle=1 rng_core.default_quality=500"
    apks="$apks rng-tools xen xen-hypervisor syslinux"
    arch="x86_64"

    apkovl="genapkovl-safecor.sh"
}