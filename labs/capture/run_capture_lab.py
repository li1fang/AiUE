from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AIUE_ROOT = SCRIPT_DIR.parents[1]
CORE_ROOT = AIUE_ROOT / "core" / "python"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from aiue_core.policy import derive_capture_policy
from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from capture_analysis import annotate_motion_inconclusive, evaluate_capture_entry
from capture_matrix import SCENARIOS, generate_capture_experiments


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Run AiUE capture lab experiments.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--suite", default="weapon_split")
    parser.add_argument("--output-root")
    parser.add_argument("--experiment-limit", type=int)
    parser.add_argument("--package-id")
    parser.add_argument("--focus", choices=["completion"])
    return parser.parse_args()


def host_auto_ue_cli_path(workspace: dict) -> Path:
    return Path(workspace["paths"]["unreal_project_root"]).resolve() / "auto_ue_cli.ps1"


def suite_report_root(workspace: dict, suite_name: str) -> Path:
    return Path(workspace["paths"]["conversion_root"]).resolve() / "_ue_suite_reports" / suite_name


def ready_host_package_ids(suite_root: Path, explicit_package_id: str | None = None) -> list[str]:
    if explicit_package_id:
        return [explicit_package_id]
    equipment_report = load_json(suite_root / "ue_equipment_assets_report.json")
    return [
        entry["character_package_id"]
        for entry in equipment_report.get("host_blueprints") or []
        if entry.get("has_ready_weapon_pairs")
    ]


def default_output_root(workspace: dict, suite_name: str) -> Path:
    aiue_root = Path(workspace["paths"].get("aiue_repo_root") or AIUE_ROOT).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return aiue_root / "Saved" / "capture_lab" / suite_name / run_id


def run_experiment(workspace: dict, suite_name: str, package_id: str, experiment: dict, experiment_root: Path) -> dict:
    host_wrapper = host_auto_ue_cli_path(workspace)
    capture_root = experiment_root / "captures"
    summary_root = experiment_root / "suite"
    summary_path = suite_report_root(workspace, suite_name) / "ue_suite_summary.json"
    scenarios = experiment["scenario_order"]
    scenario_sets = [[scenario] for scenario in scenarios] if experiment["scenario_scheduling"] == "single_scenario" else [list(scenarios)]
    action_results = []
    for index, scenario_names in enumerate(scenario_sets, start=1):
        output_path = experiment_root / f"run-scene-sweep_{index}.json"
        params = {
            "summary": str(summary_path),
            "package_id": package_id,
            "validation_mode": "editor_world_scene_sweep",
            "enable_capture": True,
            "capture_root": str(capture_root),
            "suite_output": str(summary_root / f"ue_animation_suite_summary_{index}.json"),
            "capture_manifest_output": str(summary_root / f"ue_capture_manifest_{index}.json"),
            "preferred_capture_mode": workspace["probe"].get("preferred_capture_mode", "editor_rendered"),
            "capture_delay_seconds": experiment["capture_delay_seconds"],
            "camera_lifecycle": experiment["camera_lifecycle"],
            "level_lifecycle": experiment["level_lifecycle"],
            "scenario_names": scenario_names,
            "scenario_scheduling": experiment["scenario_scheduling"],
            "completion_strategy": experiment["completion_strategy"],
            "settle_timeout_seconds": experiment["settle_timeout_seconds"],
            "file_stability_window_seconds": experiment["file_stability_window_seconds"],
            "viewport_pump_interval_seconds": experiment["viewport_pump_interval_seconds"],
            "quit_barrier_seconds": experiment["quit_barrier_seconds"],
        }
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(host_wrapper),
            "run",
            "-WorkspaceConfig",
            workspace["config_path"],
            "-Mode",
            experiment["mode"],
            "-Command",
            "run-scene-sweep",
            "-ParamsJson",
            json.dumps(params, ensure_ascii=False, separators=(",", ":")),
            "-OutputPath",
            str(output_path),
            "-PostExitFinalizeWaitSeconds",
            str(experiment["finalize_wait_seconds"]),
        ]
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        action_results.append(
            {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "output_path": str(output_path),
            }
        )

    raw_entries = []
    for manifest_path in sorted(summary_root.glob("ue_capture_manifest_*.json")):
        payload = load_json(manifest_path)
        raw_entries.extend(payload.get("entries") or [])
    evaluated_entries = annotate_motion_inconclusive([evaluate_capture_entry(entry) for entry in raw_entries])
    valid_images = sum(1 for entry in evaluated_entries if entry.get("valid_capture"))
    late_captures = sum(1 for entry in evaluated_entries if entry.get("late_capture"))
    motion_inconclusive = sum(1 for entry in evaluated_entries if entry.get("motion_inconclusive"))
    captured_before_report = sum(1 for entry in evaluated_entries if entry.get("captured_before_report"))
    captured_after_report_before_exit = sum(1 for entry in evaluated_entries if entry.get("captured_after_report_before_exit"))
    captured_after_exit = sum(1 for entry in evaluated_entries if entry.get("captured_after_exit"))
    scenario_success = {
        scenario: sum(1 for entry in evaluated_entries if entry.get("scenario") == scenario and entry.get("valid_capture"))
        for scenario in SCENARIOS
    }
    return {
        "package_id": package_id,
        "config": experiment,
        "experiment_root": str(experiment_root),
        "action_results": action_results,
        "capture_entries": evaluated_entries,
        "counts": {
            "capture_entries": len(evaluated_entries),
            "valid_images": valid_images,
            "late_captures": late_captures,
            "motion_inconclusive": motion_inconclusive,
            "captured_before_report": captured_before_report,
            "captured_after_report_before_exit": captured_after_report_before_exit,
            "captured_after_exit": captured_after_exit,
        },
        "scenario_success": scenario_success,
        "supports_motion": motion_inconclusive == 0 and valid_images > 0,
        "confidence": round(min(0.95, 0.35 + (valid_images * 0.08) - (motion_inconclusive * 0.05)), 3),
    }


def rank_experiments(experiments: list[dict]) -> list[dict]:
    def score_key(item: dict):
        counts = item["counts"]
        preferred_mode = 1 if item["config"]["mode"] == "editor_rendered" else 0
        return (
            counts["captured_before_report"],
            counts["valid_images"],
            -counts["late_captures"],
            -counts["captured_after_exit"],
            -counts["motion_inconclusive"],
            preferred_mode,
            -float(item["config"]["capture_delay_seconds"]),
        )

    return sorted(experiments, key=score_key, reverse=True)


def summarize_scenarios(experiments: list[dict]) -> dict:
    summary = {}
    for scenario in SCENARIOS:
        entries = [
            entry
            for experiment in experiments
            for entry in (experiment.get("capture_entries") or [])
            if entry.get("scenario") == scenario
        ]
        valid_entries = [entry for entry in entries if entry.get("valid_capture")]
        late_entries = [entry for entry in valid_entries if entry.get("late_capture")]
        motion_entries = [entry for entry in valid_entries if entry.get("motion_inconclusive")]
        before_report_entries = [entry for entry in valid_entries if entry.get("captured_before_report")]
        after_report_entries = [entry for entry in valid_entries if entry.get("captured_after_report_before_exit")]
        after_exit_entries = [entry for entry in valid_entries if entry.get("captured_after_exit")]
        packages = sorted({entry.get("package_id") for entry in entries if entry.get("package_id")})
        valid_packages = sorted({entry.get("package_id") for entry in valid_entries if entry.get("package_id")})
        valid_by_mode = {}
        for mode in ("cmd_rendered", "editor_rendered"):
            mode_valid = 0
            for experiment in experiments:
                if experiment.get("config", {}).get("mode") != mode:
                    continue
                mode_valid += sum(
                    1
                    for entry in (experiment.get("capture_entries") or [])
                    if entry.get("scenario") == scenario and entry.get("valid_capture")
                )
            valid_by_mode[mode] = mode_valid
        total = len(entries)
        valid_count = len(valid_entries)
        summary[scenario] = {
            "entries": total,
            "valid_images": valid_count,
            "late_captures": len(late_entries),
            "motion_inconclusive": len(motion_entries),
            "captured_before_report": len(before_report_entries),
            "captured_after_report_before_exit": len(after_report_entries),
            "captured_after_exit": len(after_exit_entries),
            "packages_seen": len(packages),
            "packages_with_valid_capture": len(valid_packages),
            "success_rate": round((valid_count / total), 4) if total else 0.0,
            "late_capture_rate": round((len(late_entries) / valid_count), 4) if valid_count else 0.0,
            "motion_inconclusive_rate": round((len(motion_entries) / valid_count), 4) if valid_count else 0.0,
            "captured_before_report_rate": round((len(before_report_entries) / valid_count), 4) if valid_count else 0.0,
            "captured_after_report_before_exit_rate": round((len(after_report_entries) / valid_count), 4) if valid_count else 0.0,
            "captured_after_exit_rate": round((len(after_exit_entries) / valid_count), 4) if valid_count else 0.0,
            "valid_by_mode": valid_by_mode,
            "packages": packages,
            "valid_packages": valid_packages,
        }
    ranked = sorted(
        summary.items(),
        key=lambda item: (
            item[1]["success_rate"],
            -item[1]["late_capture_rate"],
            -item[1]["motion_inconclusive_rate"],
            item[1]["packages_with_valid_capture"],
        ),
        reverse=True,
    )
    top_rate = ranked[0][1]["success_rate"] if ranked else 0.0
    top_scenarios = [name for name, item in ranked if item["success_rate"] == top_rate]
    return {
        "scenarios": summary,
        "ranking": [name for name, _ in ranked],
        "best_scenarios": top_scenarios,
        "best_success_rate": top_rate,
        "conclusion": (
            "jump_land_1cycle_is_not_uniquely_more_stable"
            if "jump_land_1cycle" not in top_scenarios and ranked
            else "jump_land_1cycle_ties_for_best_or_better"
        ),
    }


def summarize_completion_strategies(experiments: list[dict]) -> dict:
    summary = {}
    for experiment in experiments:
        strategy = experiment.get("config", {}).get("completion_strategy") or "passive_poll"
        bucket = summary.setdefault(
            strategy,
            {
                "experiments": 0,
                "packages": set(),
                "valid_images": 0,
                "captured_before_report": 0,
                "captured_after_report_before_exit": 0,
                "captured_after_exit": 0,
                "late_captures": 0,
                "motion_inconclusive": 0,
                "modes": set(),
            },
        )
        bucket["experiments"] += 1
        bucket["packages"].add(experiment.get("package_id"))
        bucket["modes"].add(experiment.get("config", {}).get("mode"))
        counts = experiment.get("counts", {})
        for key in (
            "valid_images",
            "captured_before_report",
            "captured_after_report_before_exit",
            "captured_after_exit",
            "late_captures",
            "motion_inconclusive",
        ):
            bucket[key] += int(counts.get(key, 0))

    normalized = {}
    for strategy, bucket in summary.items():
        valid_images = bucket["valid_images"]
        normalized[strategy] = {
            "experiments": bucket["experiments"],
            "packages": sorted(bucket["packages"]),
            "modes": sorted(item for item in bucket["modes"] if item),
            "valid_images": valid_images,
            "captured_before_report": bucket["captured_before_report"],
            "captured_after_report_before_exit": bucket["captured_after_report_before_exit"],
            "captured_after_exit": bucket["captured_after_exit"],
            "late_captures": bucket["late_captures"],
            "motion_inconclusive": bucket["motion_inconclusive"],
            "captured_before_report_rate": round((bucket["captured_before_report"] / valid_images), 4) if valid_images else 0.0,
            "captured_after_report_before_exit_rate": round((bucket["captured_after_report_before_exit"] / valid_images), 4) if valid_images else 0.0,
            "captured_after_exit_rate": round((bucket["captured_after_exit"] / valid_images), 4) if valid_images else 0.0,
        }
    ranking = sorted(
        normalized.items(),
        key=lambda item: (
            item[1]["captured_before_report_rate"],
            -item[1]["captured_after_exit_rate"],
            -item[1]["motion_inconclusive"],
            item[1]["valid_images"],
        ),
        reverse=True,
    )
    return {
        "strategies": normalized,
        "ranking": [name for name, _ in ranking],
        "best_strategy": ranking[0][0] if ranking else None,
    }


def write_matrix_csv(path: Path, experiments: list[dict]):
    fieldnames = [
        "package_id",
        "mode",
        "level_lifecycle",
        "camera_lifecycle",
        "scenario_scheduling",
        "completion_strategy",
        "capture_delay_seconds",
        "settle_timeout_seconds",
        "file_stability_window_seconds",
        "viewport_pump_interval_seconds",
        "quit_barrier_seconds",
        "finalize_wait_seconds",
        "valid_images",
        "captured_before_report",
        "captured_after_report_before_exit",
        "captured_after_exit",
        "late_captures",
        "motion_inconclusive",
        "supports_motion",
        "confidence",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for experiment in experiments:
            writer.writerow(
                {
                    "package_id": experiment["package_id"],
                    "mode": experiment["config"]["mode"],
                    "level_lifecycle": experiment["config"]["level_lifecycle"],
                    "camera_lifecycle": experiment["config"]["camera_lifecycle"],
                    "scenario_scheduling": experiment["config"]["scenario_scheduling"],
                    "completion_strategy": experiment["config"]["completion_strategy"],
                    "capture_delay_seconds": experiment["config"]["capture_delay_seconds"],
                    "settle_timeout_seconds": experiment["config"]["settle_timeout_seconds"],
                    "file_stability_window_seconds": experiment["config"]["file_stability_window_seconds"],
                    "viewport_pump_interval_seconds": experiment["config"]["viewport_pump_interval_seconds"],
                    "quit_barrier_seconds": experiment["config"]["quit_barrier_seconds"],
                    "finalize_wait_seconds": experiment["config"]["finalize_wait_seconds"],
                    "valid_images": experiment["counts"]["valid_images"],
                    "captured_before_report": experiment["counts"]["captured_before_report"],
                    "captured_after_report_before_exit": experiment["counts"]["captured_after_report_before_exit"],
                    "captured_after_exit": experiment["counts"]["captured_after_exit"],
                    "late_captures": experiment["counts"]["late_captures"],
                    "motion_inconclusive": experiment["counts"]["motion_inconclusive"],
                    "supports_motion": experiment["supports_motion"],
                    "confidence": experiment["confidence"],
                }
            )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    experiments = generate_capture_experiments(focus=args.focus)
    if args.experiment_limit:
        experiments = experiments[: args.experiment_limit]
    suite_root = suite_report_root(workspace, args.suite)
    package_ids = ready_host_package_ids(suite_root, explicit_package_id=args.package_id)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, args.suite)
    output_root.mkdir(parents=True, exist_ok=True)

    results = []
    experiment_index = 0
    for package_id in package_ids:
        for experiment in experiments:
            experiment_index += 1
            experiment_root = output_root / f"{experiment_index:03d}_{package_id}"
            results.append(run_experiment(workspace, args.suite, package_id, experiment, experiment_root))

    ranked = rank_experiments(results)
    scenario_summary = summarize_scenarios(results)
    completion_strategy_summary = summarize_completion_strategies(results)
    capabilities = load_json(Path(workspace["paths"]["capability_probe_root"]) / "latest_capabilities.json")
    policy = derive_capture_policy(capabilities, {"ranked_experiments": ranked, "run_id": output_root.name}, workspace["probe"].get("preferred_capture_mode", "editor_rendered"))
    matrix_path = output_root / "aiue_capture_lab_matrix.csv"
    policy_path = output_root / "recommended_capture_policy.json"
    report_path = output_root / "aiue_capture_lab_report.json"
    write_matrix_csv(matrix_path, results)
    policy_payload = with_report_envelope(
        policy,
        "aiue_capture_policy",
        workflow_pack="core",
        compatibility=make_compatibility_block(
            "aiue_capture_policy",
            legacy_fields=["recommended_capture_mode"],
            notes=["derived_from_capture_lab"],
        ),
    )
    write_json(policy_path, policy_payload)
    write_json(
        report_path,
        with_report_envelope(
            {
                "generated_at_utc": now_utc(),
                "run_id": output_root.name,
                "suite_name": args.suite,
                "run_root": str(output_root),
                "matrix_csv_path": str(matrix_path),
                "recommended_capture_policy_path": str(policy_path),
                "counts": {
                    "packages": len(package_ids),
                    "experiments": len(results),
                    "valid_images": sum(item["counts"]["valid_images"] for item in results),
                    "late_captures": sum(item["counts"]["late_captures"] for item in results),
                    "motion_inconclusive": sum(item["counts"]["motion_inconclusive"] for item in results),
                    "captured_before_report": sum(item["counts"]["captured_before_report"] for item in results),
                    "captured_after_report_before_exit": sum(item["counts"]["captured_after_report_before_exit"] for item in results),
                    "captured_after_exit": sum(item["counts"]["captured_after_exit"] for item in results),
                },
                "focus": args.focus,
                "scenario_summary": scenario_summary,
                "completion_strategy_summary": completion_strategy_summary,
                "experiments": results,
                "ranked_experiments": ranked,
            },
            "aiue_capture_lab_report",
            workflow_pack="pmx_pipeline",
            compatibility=make_compatibility_block(
                "aiue_capture_lab_report",
                notes=["capture_lab_is_advisory_until_release_gate"],
            ),
        ),
    )
    latest_root = output_root.parent
    write_json(latest_root / "latest_capture_lab_report.json", load_json(report_path))
    write_json(latest_root / "latest_recommended_capture_policy.json", policy_payload)
    if capabilities:
        capabilities["capture_policy"] = policy_payload
        capabilities["recommended_capture_mode"] = policy.get("recommended_mode")
        write_json(Path(workspace["paths"]["capability_probe_root"]) / "latest_capabilities.json", capabilities)
    print(f"AiUE capture lab report written to: {report_path}")


if __name__ == "__main__":
    main()
