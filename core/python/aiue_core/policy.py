from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    PACKAGE_ROOT = Path(__file__).resolve().parents[1]
    if str(PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_ROOT))
    from aiue_core.registry import capture_entries_by_mode
    from aiue_core.report_writer import make_compatibility_block, with_report_envelope
    from aiue_core.schema_utils import load_json, write_json
else:
    from .registry import capture_entries_by_mode
    from .report_writer import make_compatibility_block, with_report_envelope
    from .schema_utils import load_json, write_json


DEFAULT_SCENARIO_ORDER = ["idle_2s", "walk_forward_2s", "run_forward_2s", "jump_land_1cycle"]


def derive_capture_policy(capabilities_payload: dict | None = None, lab_report: dict | None = None, preferred_capture_mode: str = "editor_rendered") -> dict:
    entries = capture_entries_by_mode(capabilities_payload or {})
    preferred_entry = entries.get(preferred_capture_mode)
    reasoning = []
    derived_from = []
    policy = {
        "recommended_mode": preferred_capture_mode,
        "recommended_level_lifecycle": "reuse_level",
        "recommended_camera_lifecycle": "reuse_camera",
        "recommended_scenario_order": list(DEFAULT_SCENARIO_ORDER),
        "recommended_completion_strategy": "passive_poll",
        "recommended_capture_delay_seconds": 0.2,
        "recommended_settle_timeout_seconds": 6.0,
        "recommended_file_stability_window_seconds": 0.75,
        "recommended_viewport_pump_interval_seconds": 0.2,
        "recommended_quit_barrier_seconds": 2,
        "recommended_finalize_wait_seconds": int((capabilities_payload or {}).get("capture_finalize_wait_seconds") or 8),
        "confidence": 0.35,
        "derived_from": derived_from,
        "policy_reasoning": reasoning,
    }

    if capabilities_payload:
        derived_from.append(f"capabilities:{capabilities_payload.get('run_id')}")
    if lab_report:
        derived_from.append(f"capture_lab:{lab_report.get('run_id', 'latest')}")

    if preferred_entry and preferred_entry.get("reliable"):
        policy["recommended_mode"] = preferred_capture_mode
        policy["confidence"] = 0.75
        reasoning.append("preferred_capture_mode_is_reliable")
    elif preferred_entry and preferred_entry.get("callable"):
        policy["recommended_mode"] = preferred_capture_mode
        policy["confidence"] = 0.55
        reasoning.append("preferred_capture_mode_is_callable_but_unstable")
    else:
        reliable_entry = next((entry for entry in entries.values() if entry.get("reliable")), None)
        callable_entry = next((entry for entry in entries.values() if entry.get("callable")), None)
        if reliable_entry:
            policy["recommended_mode"] = reliable_entry.get("mode")
            policy["confidence"] = 0.7
            reasoning.append("fallback_to_first_reliable_capture_mode")
        elif callable_entry:
            policy["recommended_mode"] = callable_entry.get("mode")
            policy["confidence"] = 0.5
            reasoning.append("fallback_to_first_callable_capture_mode")
        else:
            reasoning.append("no_callable_capture_mode_detected")

    if lab_report:
        ranked = list(lab_report.get("ranked_experiments") or [])
        best = ranked[0] if ranked else None
        if best:
            config = dict(best.get("config") or {})
            policy.update(
                {
                    "recommended_mode": config.get("mode", policy["recommended_mode"]),
                    "recommended_level_lifecycle": config.get("level_lifecycle", policy["recommended_level_lifecycle"]),
                    "recommended_camera_lifecycle": config.get("camera_lifecycle", policy["recommended_camera_lifecycle"]),
                    "recommended_scenario_order": list(config.get("scenario_order") or policy["recommended_scenario_order"]),
                    "recommended_completion_strategy": config.get("completion_strategy", policy["recommended_completion_strategy"]),
                    "recommended_capture_delay_seconds": float(config.get("capture_delay_seconds", policy["recommended_capture_delay_seconds"])),
                    "recommended_settle_timeout_seconds": float(config.get("settle_timeout_seconds", policy["recommended_settle_timeout_seconds"])),
                    "recommended_file_stability_window_seconds": float(config.get("file_stability_window_seconds", policy["recommended_file_stability_window_seconds"])),
                    "recommended_viewport_pump_interval_seconds": float(config.get("viewport_pump_interval_seconds", policy["recommended_viewport_pump_interval_seconds"])),
                    "recommended_quit_barrier_seconds": float(config.get("quit_barrier_seconds", policy["recommended_quit_barrier_seconds"])),
                    "recommended_finalize_wait_seconds": int(config.get("finalize_wait_seconds", policy["recommended_finalize_wait_seconds"])),
                    "confidence": max(float(policy["confidence"]), float(best.get("confidence", 0.6))),
                }
            )
            reasoning.append("capture_lab_best_experiment_selected")
            if best.get("supports_motion") is False:
                reasoning.append("best_experiment_has_motion_inconclusive_risk")

    return policy


def main():
    parser = argparse.ArgumentParser(description="Derive an AiUE capture policy.")
    parser.add_argument("--capabilities", help="Path to ue_capabilities.json")
    parser.add_argument("--lab-report", help="Path to aiue_capture_lab_report.json")
    parser.add_argument("--preferred-capture-mode", default="editor_rendered")
    parser.add_argument("--output", required=True, help="Output path for recommended_capture_policy.json")
    args = parser.parse_args()

    capabilities = load_json(args.capabilities) if args.capabilities else None
    lab_report = load_json(args.lab_report) if args.lab_report else None
    policy = derive_capture_policy(capabilities, lab_report, args.preferred_capture_mode)
    write_json(
        args.output,
        with_report_envelope(
            policy,
            "aiue_capture_policy",
            workflow_pack="core",
            compatibility=make_compatibility_block(
                "aiue_capture_policy",
                legacy_fields=["recommended_capture_mode"],
                notes=["policy_is_alpha_and_json_first"],
            ),
        ),
    )
    print(f"AiUE capture policy written to: {Path(args.output).expanduser().resolve()}")


if __name__ == "__main__":
    main()
