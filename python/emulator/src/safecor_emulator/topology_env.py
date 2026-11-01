"""Load and interpret a product ``topology.json`` for the emulated environment.

A product topology file (see the Safecor *Topology* documentation) defines the
product, the screen, USB, the vCPU groups, the business Domains and the
optional hardware *configurations*. The emulated environment derives from it:
the console and the :class:`~safecor_emulator.Emulator` read it to know what to
emulate, and the file is served to the product under test at
``/etc/safecor/topology.json``.

This module also resolves the DMI values that make
:func:`safecor.ConfigurationHelper.apply_configuration` match a *selected*
configuration (or match none, for the standard configuration).

The parsing here mirrors the library's own (see ``System.get_topology_struct``
and ``System.__parse_topology``) but reads the raw file structure directly, so
it does not require the fakes to be installed.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Union

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
    languages: List[str] = field(default_factory=list)
    default_language: str = "en"
    use_usb: bool = False
    screen: Screen = field(default_factory=Screen)
    business_domains: List[BusinessDomain] = field(default_factory=list)
    configuration_names: List[str] = field(default_factory=list)
    # Raw topology data (file structure), kept for DMI resolution.
    data: Dict[str, Any] = field(default_factory=dict, repr=False)

    def business_domain_names(self) -> List[str]:
        """The names of the business Domains (in declaration order)."""
        return [d.name for d in self.business_domains]


def load_topology_data(path: Union[str, Path]) -> Dict[str, Any]:
    """Read a product ``topology.json`` as a raw dict (file structure)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_environment(path: Union[str, Path]) -> Environment:
    """Parse a ``topology.json`` file into an :class:`Environment`."""
    return build_environment_from_data(load_topology_data(path))


def build_environment_from_data(data: Dict[str, Any]) -> Environment:
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


def _configurations(env_or_data) -> List[tuple]:
    """The list of ``(name, identifier)`` for every configuration."""
    data = env_or_data.data if isinstance(env_or_data, Environment) else env_or_data
    return [
        (c.get("name", ""), c.get("identifier", {}))
        for c in data.get("configurations", [])
    ]


def configuration_dmi(env_or_data, configuration: Union[str, None]) -> Dict[str, str]:
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
    dmi: Dict[str, str] = {}
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
