"""The system profile drives the OS/hardware fakes.

A profile is a plain set of values describing the (fake) machine: its UUID,
CPU count, screen size/rotation, memory, CPU frequency, kernel command line,
DMI keys and so on. Providing a profile is what makes the emulated system
deterministic and independent of the host it runs on.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Union

_DEFAULTS = {
    "uuid": "11111111-2222-3333-4444-555555555555",
    "cpu_count": 4,
    "screen_width": 1280,
    "screen_height": 720,
    "screen_rotation": 0,
    "uptime": 3600.0,
    "cpu_freq_current": 2400.0,
    "cpu_freq_min": 1200.0,
    "cpu_freq_max": 3600.0,
    "cpu_percent": 12.5,
    "mem_total": 8 * 1024 ** 3,
    "mem_available": 4 * 1024 ** 3,
    "mem_percent": 50.0,
    "mem_used": 4 * 1024 ** 3,
    "mem_free": 4 * 1024 ** 3,
    "kernel_cmdline": "BOOT_IMAGE=/vmlinuz root=/dev/xvda1 ro quiet",
    "dmi": {},
}


@dataclass
class SystemProfile:
    """Describes the characteristics of the emulated system.

    Any field may be overridden. Unknown extra fields are kept and exposed
    through :meth:`as_dict`, which is what the fakes consume.
    """

    uuid: str = _DEFAULTS["uuid"]
    cpu_count: int = _DEFAULTS["cpu_count"]
    screen_width: int = _DEFAULTS["screen_width"]
    screen_height: int = _DEFAULTS["screen_height"]
    screen_rotation: int = _DEFAULTS["screen_rotation"]
    uptime: float = _DEFAULTS["uptime"]
    cpu_freq_current: float = _DEFAULTS["cpu_freq_current"]
    cpu_freq_min: float = _DEFAULTS["cpu_freq_min"]
    cpu_freq_max: float = _DEFAULTS["cpu_freq_max"]
    cpu_percent: float = _DEFAULTS["cpu_percent"]
    mem_total: int = _DEFAULTS["mem_total"]
    mem_available: int = _DEFAULTS["mem_available"]
    mem_percent: float = _DEFAULTS["mem_percent"]
    mem_used: int = _DEFAULTS["mem_used"]
    mem_free: int = _DEFAULTS["mem_free"]
    kernel_cmdline: str = _DEFAULTS["kernel_cmdline"]
    dmi: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        """Returns the profile as a flat dictionary (what the fakes read)."""
        data = asdict(self)
        data.pop("extra", None)
        data.pop("dmi", None)
        # Merge the extra fields at the top level
        data.update(self.extra)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SystemProfile":
        """Builds a profile from a dictionary (unknown keys go to ``extra``)."""
        known = {f for f in cls.__dataclass_fields__}
        known_fields = {k: v for k, v in data.items() if k in known}
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(**known_fields, extra=extra)


def default_profile() -> SystemProfile:
    """Returns a profile populated with the default values."""
    return SystemProfile()


def load_profile(path: Union[str, Path, None]) -> SystemProfile:
    """Loads a profile from a JSON file.

    If the path is ``None`` or the file does not exist, the default profile is
    returned.
    """
    if path is None:
        return default_profile()
    p = Path(path)
    if not p.exists():
        return default_profile()
    data = json.loads(p.read_text(encoding="utf-8"))
    return SystemProfile.from_dict(data)
