"""Install OS/hardware fakes for the ``safecor`` library

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import builtins
import io
import os
import time
import types

import safecor._configuration_helper as _CH
import safecor._system as S

_patches = []

#: Virtual path the product topology is served at (what the product reads).
TOPOLOGY_PATH = "/etc/safecor/topology.json"

#: The fake files currently served by the installed fakes. Kept mutable so that
#: :func:`apply_dmi` can switch the served DMI at runtime (configuration switch).
_active_fake_files: dict[str, str] = {}


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


def _build_fake_files(profile: dict, dmi: dict | None = None) -> dict[str, str]:
    screen_w = profile.get("screen_width", 1280)
    screen_h = profile.get("screen_height", 720)
    files = {
        "/sys/class/dmi/id/product_uuid": f"{profile.get('uuid', '')}\n",
        "/sys/class/graphics/fb0/virtual_size": f"{screen_w},{screen_h}\n",
        "/proc/cmdline": f"{profile.get('kernel_cmdline', '')}\n",
    }
    # Expose the extra DMI keys if provided
    dmi = dmi or profile.get("dmi", {}) or {}
    for key, value in dmi.items():
        files[f"/sys/class/dmi/id/{key}"] = f"{value}\n"
    return files


def install_fakes(
    profile: dict,
    topology_content: str | None = None,
    domains: list[str] | None = None,
    dmi: dict | None = None,
):
    """Install the OS/hardware fakes driven by ``profile`` (a dict).

    If fakes are already installed they are replaced.

    :param profile: the flat hardware characteristics (see ``SystemProfile.as_dict``).
    :param topology_content: optional product topology JSON to serve at
        ``/etc/safecor/topology.json`` so the product under test reads it.
    :param domains: optional list of business Domain names to add to the
        (fake) ``LibvirtHelper.get_domains()`` (in addition to Dom0 + sys-usb).
    :param dmi: optional dict of DMI key -> value to serve at
        ``/sys/class/dmi/id/<key>`` (drives
        ``ConfigurationHelper.apply_configuration``).
    """
    if _patches:
        _unpatch()

    screen_w = profile.get("screen_width", 1280)
    screen_h = profile.get("screen_height", 720)
    rotation = profile.get("screen_rotation", 0)
    dmi = dmi or profile.get("dmi", {}) or {}
    business_domains = list(domains) if domains else []

    # --- fake psutil -------------------------------------------------------
    class FakeCpuFreq:
        current = float(profile.get("cpu_freq_current", 2400.0))
        min = float(profile.get("cpu_freq_min", 1200.0))
        max = float(profile.get("cpu_freq_max", 3600.0))

    class FakeVirtualMemory:
        total = int(profile.get("mem_total", 8 * 1024**3))
        available = int(profile.get("mem_available", 4 * 1024**3))
        percent = float(profile.get("mem_percent", 50.0))
        used = int(profile.get("mem_used", 4 * 1024**3))
        free = int(profile.get("mem_free", 4 * 1024**3))

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
            result = {
                "Dom0": _FakeDomain("Dom0", [0]),
                "sys-usb": _FakeDomain("sys-usb", [0]),
            }
            for name in business_domains:
                if name not in result:
                    result[name] = _FakeDomain(name, [0])
            return result

    # --- fake xenstore-read (screen size / rotation) via subprocess.run ----
    orig_run = S.subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if (
            isinstance(cmd, (list, tuple))
            and cmd
            and os.path.basename(str(cmd[0])) == "xenstore-read"
            and len(cmd) >= 2
        ):
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
    global _active_fake_files
    real_open = builtins.open
    real_exists = os.path.exists
    _active_fake_files = _build_fake_files(profile, dmi=dmi)
    if topology_content is not None:
        _active_fake_files[TOPOLOGY_PATH] = topology_content

    def fake_open(file, mode="r", *args, **kwargs):
        key = None
        try:
            key = os.fspath(file)
        except TypeError:
            key = None
        if key in _active_fake_files:
            return io.StringIO(_active_fake_files[key])
        return real_open(file, mode, *args, **kwargs)

    # Make os.path.exists report the faked DMI / topology files, so that
    # ConfigurationHelper.apply_configuration does not skip them on hosts
    # where the real files do not exist. Conservative: only the faked paths.
    def fake_exists(path):
        try:
            if os.fspath(path) in _active_fake_files:
                return True
        except (TypeError, ValueError):
            pass
        return real_exists(path)

    _patch(S, "psutil", FakePsutil)
    _patch(S, "LibvirtHelper", FakeLibvirtHelper)
    _patch(S.subprocess, "run", fake_run)
    _patch(S, "open", fake_open)
    # The DMI reads in ConfigurationHelper use its own (built-in) `open`.
    _patch(_CH, "open", fake_open)
    _patch(os.path, "exists", fake_exists)


def apply_dmi(dmi: dict[str, str]) -> None:
    """Update the served DMI files in place (runtime configuration switch).

    Rewrites ``/sys/class/dmi/id/<key>`` in the set of faked files so that the
    next :func:`safecor.ConfigurationHelper.apply_configuration` (triggered by
    ``System.get_topology`` after a ``reset_topology``) matches the new values.
    Only meaningful while the fakes are installed.

    :param dmi: mapping of DMI key -> value (see
        :func:`safecor_emulator.topology_env.configuration_dmi`).
    """
    for key, value in dmi.items():
        _active_fake_files[f"/sys/class/dmi/id/{key}"] = f"{value}\n"


def uninstall_fakes():
    """Remove every patch installed by :func:`install_fakes`."""
    _unpatch()
