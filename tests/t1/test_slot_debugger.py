from __future__ import annotations

from pathlib import Path

from aiue_t1.report_index import build_report_index
from aiue_t1.slot_debugger import build_slot_debugger_payload


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "reports"


def test_slot_debugger_extracts_slots_and_conflicts():
    report_index = build_report_index(FIXTURE_ROOT)
    payload = build_slot_debugger_payload(report_index)
    assert payload["package_count"] == 1
    package = payload["packages"][0]
    slot_names = [slot["slot_name"] for slot in package["slots"]]
    assert slot_names == ["weapon", "clothing", "fx"]
    fx_slot = next(slot for slot in package["slots"] if slot["slot_name"] == "fx")
    assert fx_slot["binding"]["item_kind"] == "niagara_system"
    assert len(fx_slot["slot_conflicts"]) == 1
    assert len(fx_slot["superseded_bindings"]) == 1
