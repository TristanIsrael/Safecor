# How to install Alpine Linux on a machine equipped with an Intel WLAN

In Alpine 3.24 the Intel firmwares are not available during the install. We need to install it before the boot process.

## Identify the missing firmware

In the root shell type:

```
# dmesg | grep firmware
```

Find the line containing the error message `Direct firmware load for iwlwifi-[...].ucode failed with error -2`.

Notice the complete file name `iwlwifi-[...].ucode`.

## Install the firmware files

In the root shell install the requested apks:

```
# cp /media/sda/apks/x86_64/linux-firmware-intel-20260519-r0.apk /tmp

# cd /tmp

# tar xvzf linux-firmware-intel-20260519-r0.apk

# echo "/tmp/lib/firmware" > /sys/module/firmware_class/parameters/path

# modprobe -r iwlwifi

# modprobe iwlwifi

# ip link
```

With the last command, the `wlan0` network interface should appear.