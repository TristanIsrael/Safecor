profile_safecor() {
    profile_standard

    title="Kernel alpine-virt customized for Safecor"
	desc="ISO image based on Alpine standard flavour virt
        with a kernel, modloop and initramfs
        patched for Safecor Domains"	
	arch="x86_64"
		
    kernel_flavors="safecor-virt"
    syslinux_serial="0 115200"
}
