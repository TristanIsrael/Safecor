"""Install OS/hardware fakes for the ``safecor`` library.

The design goal is to keep the ``safecor`` library completely untouched. The
fakes are installed *from the outside* by patching the module-level OS
touch-points of ``safecor._system``:

- ``psutil``            -- CPU / memory / boot-time metrics
- ``LibvirtHelper``     -- CPU count and domain list
- ``subprocess.run``    -- the ``xenstore-read`` screen size/rotation queries
- ``open``              -- sysfs reads (``product_uuid``, ``fb0``) and the
                           ``/proc/cmdline`` / ``/proc/mounts`` files

Every patch is recorded and fully reversed by :func:`uninstall_fakes`, so the
same process can run with or without emulation.

The fakes are driven by a plain ``dict`` (see :meth:`SystemProfile.as_dict`).
"""

import builtins
import io
import os
import time
import types
from typing import Dict

import safecor._system as S

_patches = []


def _patch(obj, attr, new):
    orig = getattr(obj, attr, None)
    had = hasattr(obj, attr)
    _patches.append((obj, attr, orig, had))
    setattr(obj, attr, new)


def _unpatch():
    for obj, attr, orig, had in reversed(_patches):
        if had:
            setattr(obj, attr, orig)
        else:
            try:
                delattr(obj, attr)
            except AttributeError:
                pass
    _patches.clear()


def _build_fake_files(profile: dict) -> Dict[str, str]:
    screen_w = profile.get("screen_width", 1280)
    screen_h = profile.get("screen_height", 720)
    files = {
        "/sys/class/dmi/id/product_uuid": f"{profile.get('uuid', '')}\n",
        "/sys/class/graphics/fb0/virtual_size": f"{screen_w},{screen_h}\n",
        "/proc/cmdline": f"{profile.get('kernel_cmdline', '')}\n",
    }
    # Expose the extra DMI keys if provided
    dmi = profile.get("dmi", {}) or {}
    for key, value in dmi.items():
        files[f"/sys/class/dmi/id/{key}"] = f"{value}\n"
    return files


def install_fakes(profile: dict):
    """Install the OS/hardware fakes driven by ``profile`` (a dict).

    If fakes are already installed they are replaced.
    """
    if _patches:
        _unpatch()

    screen_w = profile.get("screen_width", 1280)
    screen_h = profile.get("screen_height", 720)
    rotation = profile.get("screen_rotation", 0)

    # --- fake psutil -------------------------------------------------------
    class FakeCpuFreq:
        current = float(profile.get("cpu_freq_current", 2400.0))
        min = float(profile.get("cpu_freq_min", 1200.0))
        max = float(profile.get("cpu_freq_max", 3600.0))

    class FakeVirtualMemory:
        total = int(profile.get("mem_total", 8 * 1024 ** 3))
        available = int(profile.get("mem_available", 4 * 1024 ** 3))
        percent = float(profile.get("mem_percent", 50.0))
        used = int(profile.get("mem_used", 4 * 1024 ** 3))
        free = int(profile.get("mem_free", 4 * 1024 ** 3))

    class FakePsutil:
        @staticmethod
        def cpu_freq():
            return FakeCpuFreq()

        @staticmethod
        def cpu_percent(interval=None, percpu=False):
            return float(profile.get("cpu_percent", 12.5))

        @staticmethod
        def virtual_memory():
            return FakeVirtualMemory()

        @staticmethod
        def boot_time():
            return time.time() - float(profile.get("uptime", 86400.0))

        @staticmethod
        def sensors_battery():
            return None

    # --- fake libvirt helper (cpu count + domains) -------------------------
    class _FakeDomain:
        def __init__(self, name, cpu_affinity):
            self.name = name
            self.cpu_affinity = cpu_affinity

    class FakeLibvirtHelper:
        @staticmethod
        def get_cpu_count():
            return int(profile.get("cpu_count", 4))

        @staticmethod
        def get_domains():
            return {
                "Dom0": _FakeDomain("Dom0", [0]),
                "sys-usb": _FakeDomain("sys-usb", [0]),
            }

    # --- fake xenstore-read (screen size / rotation) via subprocess.run ----
    orig_run = S.subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if (isinstance(cmd, (list, tuple)) and cmd
                and os.path.basename(str(cmd[0])) == "xenstore-read"
                and len(cmd) >= 2):
            key = str(cmd[1])
            if key.endswith("screen_size"):
                out = f"{screen_w},{screen_h}"
            elif key.endswith("screen_rotation"):
                out = str(rotation)
            else:
                out = ""
            return types.SimpleNamespace(stdout=out, stderr="", returncode=0)
        return orig_run(cmd, *args, **kwargs)

    # --- fake sysfs / proc reads via `open` --------------------------------
    real_open = builtins.open
    fake_files = _build_fake_files(profile)

    def fake_open(file, mode="r", *args, **kwargs):
        key = None
        try:
            key = os.fspath(file)
        except TypeError:
            key = None
        if key in fake_files:
            return io.StringIO(fake_files[key])
        return real_open(file, mode, *args, **kwargs)

    _patch(S, "psutil", FakePsutil)
    _patch(S, "LibvirtHelper", FakeLibvirtHelper)
    _patch(S.subprocess, "run", fake_run)
    _patch(S, "open", fake_open)


def uninstall_fakes():
    """Remove every patch installed by :func:`install_fakes`."""
    _unpatch()
