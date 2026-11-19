# Run 12

Preparation:
- [x] Rebuild the `safecor-core`, `safecor-lib`, `safecor-domu-base` and `safecor-sys-usb` packages from `version-2`
- [x] On Dom0: `apk update && apk add safecor-core`, then `apk info -v safecor-core`
- [x] In the Saphir repository: add `pango cairo gdk-pixbuf2.0` to the depends of the `saphir` package and rebuild
- [x] Full cold boot in debug mode

Verification:
- [x] Verify all Domains (sys-usb, business, saphir-gui) boot without hanging
  - sys-usb is started but the controller is not started. The initd is crashed.
  - I suspect a permission issue: if I start it manually with the command `su -s /bin/sh svc-sys-usb-controller -c "python3 /usr/lib/safecor/bin/safecor-sys-usb-controller.py"` I get the error: 
```
Error loading shared library libpython3.14.so.1.0: Permission denied (needed by /usr/bin/python3)
Error relocating /usr/bin/python3: Py_BytesMain: symbol not found
```
- [x] Verify the GUI display and the Saphir app start (report generation enabled)
  - The GUI app starts in fullscreen but there is no input (mouse or touch)
  - I can see its messages on the bus
- [x] Verify the GUI domain console: `xl console <gui domain>` shows a login prompt on ttyS0 -> OK
- [x] In saphir-gui, verify the packages mount and the apkovl flow: `cat /etc/fstab`, `mount | grep packages`, `cat /proc/cmdline`, `cat /etc/hostname` — to reconcile with the repository template fstab (`/dev/xvde`) vs the HVM packages vdev (`sde`) -> In domains all the disks appear as `xvd*` even when they are declared `sd*`
- [x] Verify the debug tty after an `xl reboot sys-usb` (the representative API path, not destroy/create)
  - The reboot with the message `system/workflow/restart_domain/request` does not work
  - I rebooter on Dom0 with the script `/usr/lib/safecor/bin/reboot-domain.sh sys-usb` and the domain rebooted but the message `Safecor/reboot-domain.sh: Failed to get domid for sys-usb after reboot`. The message appeared before `sys-usb` had finish turning off.
- [x] Verify the file read on a USB storage from a Domain (direct mount), including a start without USB storage connected — a manual start of `start-direct-mount.py` now reports the failure reason on stderr
  - Tried from `saphir-av-eset`: no mount. Manual start of `start-direct-mount.py` fails after a timeout and no message is sent on the bus.
```
direct-mount: DirectMountManager: timeout waiting for my_config response
direct-mount: DirectMountManager: this domain does not have direct_mount enabled
```
  - The antivirus controller on `saphir-av-eset` answers to the request `system/discover/components/request` so the vchan is ok.
  - See the analysis in the discussion below.

Discussion:
- How the concurrency is managed on the vchan in a Domain? For example if a controller is already started it "takes" the socket, and what happens if another process wants to connect to it after, like the `direct-mount`?
  - Answer: there is a race condition on the socket. If I stop the `av-controller` and I start the `direct-mount` I can see the request on the bus: `system/topology/my_config/request`.
- The SFTP vchan is not working:
  - When I start `direct-mount` I receive no error, the message says that the `Direct mount is ready at /media/usb`, but it is not. When I call `df` it remains stucked.
  - When I check the values of the xenstore at `/local/domain/system/vchan` from inside the `saphir-av-eset` I can see that there is no vchan for sftp.
  - In `sys-usb` I believe the socat command that creates the socket is started after the `vchan-socket-proxy`, but `vchan-socket-proxy` needs to connect to the socket created by socat. So it is reversed in `safecor-vchan-sftp.py` in the package `safecor-sys-usb`.
  - Additionally there might be a problem of permission on the xenstore path, but I am not 100% sure. The xenstore path must be accessible `write` and `read`. -> I modifed the permissions in `set-xenstore-permissions.sh`.
  - When I start the `socat` command then the `vchan-socket-proxy` command I get a repeating error related to the unavailability of `sftp-server`, maybe because it is not in the `chroot` and the binary and its dependencies are not available in the `chroot`
  - In `saphir-av-eset` the command `xenstore-ls /local/domain/system/vchan` returns a permission error (see xenstore permission problem above)
  - The `/media` path is the `chroot` for `sftp-server` so it should contain:
    - The `musl` library in `/media/lib`, 
    - The binary `/media/bin/sftp-server`,
    - The special device `/media/dev/null`,
    - The file `/media/etc/passwd` with `root:x:0:0:root:/root:/sbin/nologin`,
    - The binary `/sbin/nologin`
  - After all these steps the sftp tunnel works
- Security concerns about the SFTP server:
  - The sftp server starts in the chroot `/media` and it exposes all the `/media` directory. The client would expect the root to be the `/media/usb` directory because the file paths are constructed with this root and the disk name, for example `/my_disk` will be mounted under `/media/usb/my_disk` on `sys-usb`.
  - It seems that there is no way to force the sftp server to start in the subdirectory `usb` so the chroot should probably be `/media/usb`
  - It might be useful to add the `-P` filter for denied SFTP requests or `-p` for the allowed SFTP requests.
  - Also we might use the `-u` option for the umask of the created files.
  - For the read-only channels we should also add the `-R` option.

Resolution: the analysis of the seven findings and their resolutions are recorded in [test-channels-migration.md](test-channels-migration.md) (section "Run 12 resolutions"). The follow-up issues are #258 to #264.
  