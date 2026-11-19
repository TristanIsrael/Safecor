# Run 11

Preparation:
- [x] Rebuild the `safecor-core` and `safecor-sys-usb` packages from `version-2` (tip `c2bfcec`)
- [x] On Dom0: `apk update && apk add safecor-core`, then `apk info -v safecor-core` and `ls /etc/udev/rules.d/` -> OK
- [x] Full cold boot in debug mode

Verification:
- [x] Verify `/dev/xen/gntdev`, `/dev/xen/evtchn`, `/dev/xen/gntalloc` are group `safecor`, mode `0660` right after boot (no manual fix) -> OK
- [x] Verify the `vchan-socket-proxy` servers are alive with no restart loop (no `Permission denied` in `/var/log/safecor/vchan-servers.log`) -> OK
- [x] Verify all domains (sys-usb, business, sys-gui) boot without hanging
  - `sys-usb` OK
  - `saphir-av-clamav` OK
  - `saphir-av-eset` OK
  - `saphir-gui` not started
- [x] Verify the business domain console: `xl console <domid>` shows the boot log and a login prompt (hvc0)
  - `sys-usb` OK
  - `saphir-av-clamav` OK
  - `saphir-av-eset` OK
  - `saphir-gui` not started
- [x] Verify the debug tty: typing on the debug console shows the Dom0 login prompt (no manual tunnel, no cable replug) 
  - Initial boot: OK
  - After `sys-usb` restart: No more debug console
- [x] Verify the GUI domain console: `xl console <gui domain>` shows a login prompt on ttyS0 (getty enabled at provisioning) -> Not started
- [x] Verify there is no more `tcgetaddr: I/O error` getty spam in the PV/PVH domain logs
  - `sys-usb` OK
  - `saphir-av-clamav` OK
  - `saphir-av-eset` OK  
- [x] Verify the sys-usb controller sends `discover_components/response` and answers pings (via its initd, no manual relaunch) -> OK
- [x] Verify the file read on a USB storage from a Domain (direct mount), including a start without USB storage connected
  - The command `python3 /usr/lib/safecor/bin/start-direct-mount.py` on a business domain return the error code 1, there is no log to analyse.
- [x] Verify the GUI display -> KO
  - Not starting because `qemu-xen doesn't support read-only IDE disk drivers` -> Fixed
  - The command `xrandr --output Virtual-1 --display :0 --mode $resolution` returns an error `xrandr: cannot find mode 1280x800`.
    - QEMU should use the `stdvga` mode -> Fixed.
  - Saphir GUI app does not start because of a (packaging) error:
```
WeasyPrint could not import some external libraries. Please carefully follow the installation steps before reporting an issue:
https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation
https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting

-----

Report generation is disabled due to a missing dependency
The font MaterialIconsOutlined-Regular.otf has been correctly installed
The font MaterialIcons-Regular.ttf has been correctly installed
The font Inter-VariableFont_opsz_wght.ttf has been correctly installed
The font Inter-Italic-VariableFont_opsz_wght.ttf has been correctly installed
The font LED Dot-Matrix.ttf has been correctly installed
Traceback (most recent call last):
  File "main.py", line 109, in <module>
  File "Saphir/application_controller.py", line 223, in __init__
    self.__report_controller = ReportController(self)
                               ^^^^^^^^^^^^^^^^
NameError: name 'ReportController' is not defined
[PYI-2922:ERROR] Failed to execute script 'main' due to unhandled exception!
```
  
Debug TTY bisection (only if the debug console is still broken):
- Dom0: `pgrep -af "socat|getty|vchan-socket-proxy"`, `ls -l /var/run/safecor/`, then `socat - UNIX-CONNECT:/var/run/safecor/sys-usb-tty.sock` and type -> a Dom0 login prompt means the Dom0 side is healthy.
- sys-usb: `pgrep -af "vchan-socket-proxy|socat"`, `ls -l /var/run/safecor/`, `logread | grep -iE "tty|vchan"`, then `socat - UNIX-CONNECT:/var/run/safecor/tty.sock` and type -> if nothing appears, the broken link is the vchan channel (client or server), not the getty chain.

Analysis:
- The channels (vchan) migration is validated end-to-end on all PV/PVH Domains: boot, PV console (`xl console`, hvc0), Xen device node permissions (the udev fix), stable vchan servers, MQTT (`discover_components` + ping), the `packages.squashfs` repository, and no more ttyS0 getty spam.
- `saphir-gui` (HVM) did not start: `qemu-xen doesn't support read-only IDE disk drivers`. Root cause: commit `5c011e6` normalized the HVM disk vdevs to `xvdd`/`xvde`, but the HVM layout has historically been `sdd`/`sde` (SCSI). The fix restores the historical layout, adds `devtype=cdrom` on the config image, and switches the display to `vga = "stdvga"` (virtio-gpu and `gl=on` removed) -> the Domain now starts.
- GUI display: `xrandr: cannot find mode 1280x800` with virtio-gpu -> fixed by `vga = "stdvga"` (full VESA mode table).
- Saphir GUI app: WeasyPrint misses its system libraries (pango/cairo/gdk-pixbuf) -> product-level packaging fix in the `saphir` package of the Saphir repository (add `pango cairo gdk-pixbuf2.0` to its depends); the `NameError: ReportController` is a downstream symptom of the guarded import, it disappears with the dependencies.
- Debug tty after the sys-usb restart: the restart was done with a manual `xl destroy`/`xl create`, which is not representative: the API (`restart_domain`) uses `xl reboot` (in-place restart, the USB PCI passthrough is preserved). The Dom0 side is self-healing in the code (the vchan manager re-keys the servers by domid, the listening socat survives the client disconnect). To retest with the API path in run 12; if it still dies, run the bisection above.
- Direct mount rc 1 without logs: `DirectMountManager.run()` exits 1 when `start()` fails — at the time of run 11 `direct_mount` was not configured in the machine topology (it is now). The "no logs" came from the launcher printing nothing on stderr and from the MQTT log client being stopped after the `my_config` query. Fixed: the manager mirrors all its diagnostics on stderr, the openrc instance redirects its output to `/dev/null` by default, and a manual start in the domain console reports the failure reason.
- Log channel clarification: there is no dedicated log channel — logs travel over the MQTT msg channel (`system/events/*` topics), with `safecor-syslog` (rsyslog `omuxsock` + logger daemon) as the syslog feeder. `Constants.MQTT_LOG_BROKER_SOCKET` is an orphaned constant (defined, never used).

Resolution (pushed to `version-2`):
- HVM: historical `sdd`/`sde` layout restored, `devtype=cdrom` on the config image, `vga = "stdvga"` without GL (create-domains.py + sha512 recalc).
- Direct mount observability: stderr mirroring in `DirectMountManager`, `/dev/null` redirect by default in `direct-mount.initd`.
- WeasyPrint: handled in the Saphir repository (outside of this repository).