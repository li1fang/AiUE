from __future__ import annotations

from pathlib import Path

import pytest

from aiue_t2.ui import WorkbenchWindow

from tests.t2.helpers import build_fixture_pack


@pytest.mark.soak
def test_workbench_short_soak(qtbot, tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    window = WorkbenchWindow(manifest_path=pack["manifest_path"])
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.current_dump_payload()["status"] == "pass")

    for step in range(30):
        window.advance_debug_cycle(step)
        window.refresh_from_manifest()
        qtbot.wait(10_000)
        assert window.current_dump_payload()["status"] == "pass"
        assert window.current_error_codes() == []

    assert window.isVisible()
    assert window.current_dump_payload()["summary_counts"]["reports"] == 7
