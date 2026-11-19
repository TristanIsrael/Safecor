# Run 10 (aggregate of several boots)

Preparation:
- [x] Rebuild the `safecor-core` and `safecor-sys-usb` packages
- [x] On Dom0: `apk update && apk add safecor-core`, then verify
      `apk info -v safecor-core` and `ls /etc/udev/rules.d/` (to rule out
      the "stale package" hypothesis) -> `ls /etc/udev/rules.d/` gives an error event after `apk del saphir && apk update && apk add saphir` and a cold reboot in debug mode
- [x] Full cold boot in debug mode

Verification:
- [x] Verify `/dev/xen/gntdev`, `/dev/xen/evtchn`, `/dev/xen/gntalloc` are
      group `safecor`, mode `0660` right after boot (no manual fix) -> `/dev/xen/gntalloc` is still owned by root:root. -> I fixed the problem by adding udev in the dependencies and make it start during boot.
- [x] Verify the `vchan-socket-proxy` servers are alive with no restart
      loop (no `Permission denied` in `/var/log/safecor/vchan-servers.log`)
- [x] Verify the input/tty servers are alive (no `connect: Permission denied`) -> in  `sys-usb` the socat tunnel is not working. Maybe it should be synchronized with the vchan socket connection? Additionally there is an error when I create the tunnel manually with the following command: `socat /dev/ttyUSB0,raw,echo=0,b115200 UNIX-CONNECT:/var/run/safecor/tty.sock` I get the error `socat[2532] E tcgetattr(5, 0x56515e013980): Not a tty`.
- [x] Verify all domains (sys-usb, business, sys-gui) boot without hanging -> Still hanged.
- [x] Verify the sys-usb controller sends `discover_components/response` and answers pings (via its initd, no manual relaunch) -> OK
- [x] Verify the debug tty on sys-usb works
- [x] Verify the file read on a USB storage from a Domain (direct mount) -> business domains not available (console)
- [x] Verify the GUI display -> domain not available (console)

Analysis:
- The console is not active on the business domains (pvh) because they miss the kernel command parameter `console=hvc0`. -> fixed
- The business domains don't start because the kernel can't find the root filesystem. -> The ISO image was not loaded in the domain because of the `devtype=cdrom` option in the xl file. -> fixed
- The apkovl file is not correct in the business domains: always `sys-usb.apkovl.tar.gz`. -> fixed
- There were doubles in the disks declaration ( `sdd` / `xvdd`) -> fixed
- When there is no USB storage connected on the system when the business Domain starts the direct-mount crashes. There is no log to analyse. If I connect a storage and I start the direct-mount process over nothing happens either. If I start the process `python3 /usr/lib/safecor/bin/start-direct-mount.py` manually there is no error and nothing happens. -> I guess I should try again with a clean install.

Additional information:
- The Domains (all of them) keep spamming the system log about an error with `/bin/getty`: `tcgetaddr: I/O error`. We should disable the getty on `ttyS0` for the PV and PVH. It is defined in the template of the apkovl created in `safecor-core`. It is only declared for the HVM to be able to provide a console to xl.

Resolution (pushed to `version-2`, tip `c2bfcec`):
- `/dev/xen/gntalloc` root:root at boot -> `eudev` dependency + `99-safecor.rules` udev rule + udev started at boot (`cb2dd89`).
- Business domains (missing `console=hvc0`, `devtype=cdrom` on PVH, wrong apkovl, `sdd`/`xvdd` doubles) -> fixed xl configs for PVH and HVM, packages served by `packages.squashfs` on `xvde`, no more 9p shares (`5c011e6`).
- Getty `ttyS0` spam on PV/PVH -> getty disabled in the apkovl template, re-enabled at provisioning for HVM domains only (`5c011e6`).
- `Not a tty` on the manual socat test -> confirmed typo in the test command (`ttyUBS0`); with the correct name no error.
- sys-usb socat tunnel (the actual broken link of the debug tty) -> supervised loop synchronized with the vchan socket + stale PTY symlink cleanup on Dom0 (`ed4e2c0`). To validate in run 11.
- Direct-mount crash without USB storage -> retry with a clean install (run 11).