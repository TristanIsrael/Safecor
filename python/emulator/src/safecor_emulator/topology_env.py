"""Load and interpret a product ``topology.json`` for the emulated environment

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: DMI value used to guarantee that **no** configuration identifier matches,
#: so the standard topology values are applied (the "Aucune (standard)" choice).
NO_CONFIGURATION = "__EMULATOR_NO_CONFIGURATION__"


@dataclass
class BusinessDomain:
    """A business Domain declared in the topology file."""

    name: str
    app_package: str = ""
    memory: int = 0
    vcpu_group: str = ""
    temp_disk_size: int = 0
    swap_size: int = 0
    has_gui: bool = False


@dataclass
class Screen:
    """Screen settings from the topology (size comes from the framebuffer)."""

    enabled: bool = False
    rotation: int = 0
    default_focus: str = ""


@dataclass
class Environment:
    """The emulated environment derived from a product topology file."""

    product_name: str = ""
    splash_bgcolor: str = "#000000"
    languages: list[str] = field(default_factory=list)
    default_language: str = "en"
    use_usb: bool = False
    screen: Screen = field(default_factory=Screen)
    business_domains: list[BusinessDomain] = field(default_factory=list)
    configuration_names: list[str] = field(default_factory=list)
    # Raw topology data (file structure), kept for DMI resolution.
    data: dict[str, Any] = field(default_factory=dict, repr=False)

    def business_domain_names(self) -> list[str]:
        """The names of the business Domains (in declaration order)."""
        return [d.name for d in self.business_domains]


def load_topology_data(path: str | Path) -> dict[str, Any]:
    """Read a product ``topology.json`` as a raw dict (file structure)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_environment(path: str | Path) -> Environment:
    """Parse a ``topology.json`` file into an :class:`Environment`."""
    return build_environment_from_data(load_topology_data(path))


def build_environment_from_data(data: dict[str, Any]) -> Environment:
    """Build an :class:`Environment` from raw topology data (file structure)."""
    product = data.get("product", {})
    usb = data.get("usb", {})
    screen = data.get("screen", {})
    business = data.get("business", {}).get("domains", [])
    configurations = data.get("configurations", [])

    return Environment(
        product_name=product.get("name", ""),
        splash_bgcolor=product.get("splash_bgcolor", "#000000"),
        languages=list(product.get("languages", [])),
        default_language=product.get("default_language", "en"),
        use_usb=bool(usb.get("use", False)),
        screen=Screen(
            enabled=bool(screen.get("enabled", False)),
            rotation=int(screen.get("rotation", 0)),
            default_focus=screen.get("default_focus", ""),
        ),
        business_domains=[
            BusinessDomain(
                name=d.get("name", "unknown"),
                app_package=d.get("app-package", ""),
                memory=int(d.get("memory", 0)),
                vcpu_group=d.get("vcpu_group", ""),
                temp_disk_size=int(d.get("temp_disk_size", 0)),
                swap_size=int(d.get("swap_size", 0)),
                has_gui=bool(d.get("has_gui", False)),
            )
            for d in business
        ],
        configuration_names=[c.get("name", "") for c in configurations],
        data=data,
    )


def _configurations(env_or_data) -> list[tuple]:
    """The list of ``(name, identifier)`` for every configuration."""
    data = env_or_data.data if isinstance(env_or_data, Environment) else env_or_data
    return [
        (c.get("name", ""), c.get("identifier", {}))
        for c in data.get("configurations", [])
    ]


def configuration_dmi(env_or_data, configuration: str | None) -> dict[str, str]:
    """Return the DMI key -> value mapping that makes the chosen configuration match.

    ``apply_configuration`` compares the system DMI values
    (``/sys/class/dmi/id/<key>``) against each configuration's ``identifier``
    and applies the first one where **all** its keys match. To make exactly one
    configuration match (or none), every identifier key of every configuration
    is first set to a sentinel (so nothing matches), then the selected
    configuration's own keys are set to its values (so it matches).

    :param env_or_data: an :class:`Environment` or a raw topology data dict.
    :param configuration: the configuration ``name`` to select, or ``None`` /
        empty for the standard configuration (no configuration matches).
    :return: a dict of DMI key -> value to feed the fakes.
    """
    dmi: dict[str, str] = {}
    configs = _configurations(env_or_data)
    for _, identifier in configs:
        for key in identifier:
            dmi[key] = NO_CONFIGURATION
    if configuration:
        for name, identifier in configs:
            if name == configuration:
                dmi.update({key: str(value) for key, value in identifier.items()})
                break
    return dmi


def apply_configuration_settings(
    env: Environment, configuration: str | None
) -> None:
    """Apply a configuration's ``settings`` overrides onto ``env`` (in place).

    Mirrors ``safecor.ConfigurationHelper.__merge_configuration`` for the fields
    the console displays: it resets the screen and USB to the topology's base
    values, then applies the selected configuration's ``settings``
    (``screen.enabled`` / ``screen.rotation`` / ``screen.default_focus`` /
    ``usb.use``) on top. A ``None`` / empty ``configuration`` selects the
    standard environment (base values only); resetting first also makes
    re-selection idempotent.
    """
    base_screen = env.data.get("screen", {})
    env.screen.enabled = bool(base_screen.get("enabled", False))
    env.screen.rotation = int(base_screen.get("rotation", 0))
    env.screen.default_focus = base_screen.get("default_focus", "")
    env.use_usb = bool(env.data.get("usb", {}).get("use", False))

    settings: dict[str, Any] = {}
    if configuration:
        for conf in env.data.get("configurations", []):
            if conf.get("name", "") == configuration:
                settings = conf.get("settings", {}) or {}
                break

    screen = settings.get("screen", {}) or {}
    if "enabled" in screen:
        env.screen.enabled = bool(screen["enabled"])
    if "rotation" in screen:
        env.screen.rotation = int(screen["rotation"])
    if "default_focus" in screen:
        env.screen.default_focus = screen["default_focus"]
    usb = settings.get("usb", {}) or {}
    if "use" in usb:
        env.use_usb = bool(usb["use"])
