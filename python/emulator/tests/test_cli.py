"""Tests for the ``--gui`` CLI flag (Phase 3).

The headless path is unchanged and covered indirectly; here we cover the new
``--gui`` branch: it requires ``--topology`` and hands over to
:func:`safecor_emulator.gui.run_gui` with the broker options.
"""

import argparse
import sys
from unittest import mock

import pytest

from safecor_emulator import cli


def test_gui_requires_topology():
    with pytest.raises(SystemExit) as exc:
        cli.main(["--gui"])
    assert exc.value.code == 2


def test_gui_without_pyside6_gives_friendly_error(tmp_path, capsys):
    """A missing PySide6 (gui extra) exits with a hint, not an ImportError traceback."""
    topo = tmp_path / "topology.json"
    topo.write_text("{}", encoding="utf-8")
    with (
        mock.patch.dict(sys.modules, {"safecor_emulator.gui": None}),
        pytest.raises(SystemExit) as exc,
    ):
        cli.main(["--gui", "--topology", str(topo)])
    assert exc.value.code == 2
    assert "PySide6" in capsys.readouterr().err


def test_gui_launches_run_gui(tmp_path):
    topo = tmp_path / "topology.json"
    topo.write_text("{}", encoding="utf-8")
    with mock.patch("safecor_emulator.gui.run_gui", return_value=0) as run_gui:
        rc = cli.main(["--gui", "--topology", str(topo), "--port", "1884"])
    assert rc == 0
    run_gui.assert_called_once_with(
        topology_path=str(topo),
        broker_port=1884,
        host="localhost",
        reuse_broker=True,
    )


def test_gui_no_reuse_forwarded(tmp_path):
    topo = tmp_path / "topology.json"
    topo.write_text("{}", encoding="utf-8")
    with mock.patch("safecor_emulator.gui.run_gui", return_value=3) as run_gui:
        rc = cli.main(["--gui", "--topology", str(topo), "--no-reuse"])
    assert rc == 3
    assert run_gui.call_args.kwargs["reuse_broker"] is False


def test_headless_starts_and_stops():
    """Without --gui the headless core runs until interrupted, then stops."""
    with (
        mock.patch("safecor_emulator.cli.Emulator") as emulator,
        mock.patch("safecor_emulator.cli.time.sleep", side_effect=KeyboardInterrupt),
    ):
        rc = cli.main([])
    assert rc == 0
    emulator.return_value.start.assert_called_once()
    emulator.return_value.stop.assert_called_once()


@pytest.mark.parametrize("bad", ["no-equals", "=path", "name="])
def test_parse_disks_rejects_bad_format(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        cli.main(["--disk", bad])
