The Safecor emulator
====================

**The Safecor emulator** (the ``safecor-emulator`` package) lets you run
Safecor -- and any Safecor-based product -- on a plain machine, with **no Xen,
no HVM and no real hardware**.

It brings up everything the core normally provides, in software:

- a **Mosquitto** MQTT broker,
- the **mock core domains** (Dom0 and sys-usb), which answer the core MQTT
  commands (list disks, list/read/copy/create files, system info, ...) and
  operate on local directories instead of real USB hardware,
- **OS/hardware fakes** (UUID, CPU count, screen size, memory, ...) installed
  from the outside -- the :mod:`safecor` library is left completely untouched.

Use it to develop and test a Safecor-based product on a laptop, or in CI,
without the physical platform.

How it works
------------

- **Maximum separation.** The fakes are installed by patching a few module-level
  touch-points of ``safecor._system`` (``psutil``, ``LibvirtHelper``, the
  ``xenstore-read`` subprocess, and a handful of sysfs/``/proc`` reads). Every
  patch is recorded and fully reversed, so the same process can run with or
  without emulation.
- **The broker runs on port 1883.** In TCP/debug mode the Safecor MQTT client
  connects to the default MQTT port (1883). The emulator therefore reuses a
  broker already listening on 1883, and only starts its own otherwise.
- **Mock peers.** The Dom0 and sys-usb mocks are in-process MQTT clients that
  speak the same protocol as the real controllers. Each emulator instance uses
  unique MQTT client-ids, so several emulators can share one broker.

Installation
------------

The package lives in ``python/emulator``. Install it (editable) into your
virtual environment::

    pip install -e python/emulator

It requires :mod:`safecor`, ``paho-mqtt``, ``psutil`` and the ``mosquitto``
broker binary (e.g. ``apt-get install mosquitto``).

Quick start: run a product against the emulator
-----------------------------------------------

Start the emulated core in one terminal::

    safecor-emulator --disk usb0=/path/to/files

Then, in a second terminal, run your product pointed at the broker. For example,
the reference ``demo2`` app in dev mode::

    cd python/demo2/src/demo2
    DEVMODE=1 QT_QPA_PLATFORM=offscreen python main.py

``--disk NAME=PATH`` is repeatable; ``NAME`` is the disk id the product sees and
``PATH`` is the local directory that emulates that disk's contents.

Using the :class:`~safecor_emulator.Emulator` class
---------------------------------------------------

In tests or scripts, use the ``Emulator`` as a context manager::

    from safecor_emulator import Emulator, default_profile

    with Emulator(
        profile=default_profile(),
        source_disks={"usb0": "/path/to/files"},
        storage_path="/tmp/safecor/repository",
        destination_disk_path="/tmp/safecor/target",
    ) as em:
        # your product / Safecor calls run here, against the emulated core
        ...

On exit, the peers are stopped, the fakes are removed and (if the emulator
started its own broker) the broker is stopped.

System profile
--------------

A :class:`~safecor_emulator.SystemProfile` drives the OS/hardware fakes: UUID,
CPU count, screen size/rotation, memory, CPU frequency, kernel command line and
DMI keys. A bundled default is available::

    from safecor_emulator import default_profile, load_profile, SystemProfile

    profile = default_profile()
    profile = load_profile("my_profile.json")   # overrides defaults
    profile = SystemProfile(uuid="...", cpu_count=8, screen_width=1920)

See ``system_profile.default.json`` (in the package) for the full set of fields.

USB hot-plug
------------

While the emulator is running you can attach and detach disks; each operation
publishes a ``system/disks/state`` notification (``connected`` /
``disconnected``), exactly like the real sys-usb controller::

    em.attach_disk("usb1", "/path/to/more/files")
    em.detach_disk("usb1")

Fake input
----------

Keyboard and mouse input does not travel over MQTT; on real hardware it is read
from a XenBus serial socket. The emulator provides a :class:`~safecor_emulator.FakeInputDevice`
that emits events in the *same wire format* (a msgpack 4-tuple) and writes them
to a local file. Inject events and inspect them::

    em.inject_key("a")          # key press
    em.click("enter")           # press + release
    em.mouse_move(10, -5)       # relative move
    em.mouse_click("left")
    em.mouse_wheel(1)

    events = em.input.read_events()   # [[1, 1, 30, 1], ...]
    print(em.input_events_path)       # where the bytes were written

To consume them on the DomU side, point the input socket constant
(``Constants.DOMU_INPUT_SOCKET_FILEPATH``) at ``em.input_events_path``.

Using the emulator from a product test suite
--------------------------------------------

A product can use the emulated core directly from its own pytest suite. In the
product's ``conftest.py`` add::

    pytest_plugins = ["safecor_emulator.pytest_plugin"]

This exposes a session-scoped ``emulator`` fixture (a fully started ``Emulator``
with a pre-created ``disk0`` source disk) and an ``emulator_source_disk``
fixture::

    def test_my_product_lists_disks(emulator, emulator_source_disk):
        # `emulator` is running; drive your product's MQTT logic against it
        ...

Running the emulator's own tests
--------------------------------

    pytest python/emulator/tests

Notes and limitations
---------------------

- The broker must be reachable on **1883** (the Safecor client hard-codes that
  port in TCP mode). The emulator reuses an existing broker when present.
- Fake input is written to a **local file** in the XenBus wire format; it is not
  delivered to a real display or keyboard.
- The sys-usb mock's ``mount``/``unmount`` of image files uses the real
  ``mount`` command (needs root). For day-to-day emulation, prefer
  ``attach_disk`` / ``detach_disk`` for hot-plug.
