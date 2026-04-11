from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, repo_root_from_workspace, write_report_pair

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json

GATE_ID = "showcase_demo_e1_stability"
FIXED_EXECUTION_PROFILE = {
    "rerun_count": 2,
    "refresh_t1_evidence_pack": True,
    "verify_t2_latest_consumption": True,
    "required_t2_status": "pass",
    "required_t2_active_gate_id": "showcase_demo_e1",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE E1 stability gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def run_powershell_script(script_path: Path, arguments: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode, completed.stdout, completed.stderr


def parse_json_stdout(stdout: str) -> dict:
    stripped = stdout.strip()
    if not stripped:
        raise ValueError("stdout was empty")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def e1_signature(report_payload: dict) -> dict:
    per_package = []
    for item in sorted(list(report_payload.get("per_package_results") or []), key=lambda row: str(row.get("package_id") or "")):
        shot_results = sorted(list(item.get("shot_results") or []), key=lambda row: str(row.get("shot_id") or ""))
        per_package.append(
            {
                "package_id": str(item.get("package_id") or ""),
                "status": str(item.get("status") or ""),
                "hero_shot_id": str(item.get("hero_shot_id") or ""),
                "shot_ids": [str(shot.get("shot_id") or "") for shot in shot_results],
                "motion_pass_shots": int((item.get("counts") or {}).get("motion_pass_shots") or 0),
                "full_stack_before_shots": int((item.get("counts") or {}).get("full_stack_before_shots") or 0),
                "full_stack_after_shots": int((item.get("counts") or {}).get("full_stack_after_shots") or 0),
            }
        )
    counts = dict(report_payload.get("counts") or {})
    return {
        "status": str(report_payload.get("status") or ""),
        "resolved_package_ids": [str(item) for item in list(report_payload.get("resolved_package_ids") or [])],
        "counts": {
            "packages": int(counts.get("packages") or 0),
            "passing_packages": int(counts.get("passing_packages") or 0),
            "captured_before_images": int(counts.get("captured_before_images") or 0),
            "captured_after_images": int(counts.get("captured_after_images") or 0),
            "hero_shots_passed": int(counts.get("hero_shots_passed") or 0),
            "motion_pass_shots": int(counts.get("motion_pass_shots") or 0),
        },
        "per_package": per_package,
    }


def rerun_result(step_id: str, report_path: Path, latest_report_path: Path, returncode: int, stdout: str, stderr: str) -> dict:
    report_payload = load_json(report_path) if report_path.exists() else None
    return {
        "step_id": step_id,
        "status": (report_payload or {}).get("status") or ("pass" if returncode == 0 else "fail"),
        "returncode": int(returncode),
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
        "report_path": str(report_path.resolve()),
        "latest_report_path": str(latest_report_path.resolve()),
        "signature": e1_signature(report_payload or {}) if report_payload else None,
        "counts": dict((report_payload or {}).get("counts") or {}),
        "resolved_package_ids": list((report_payload or {}).get("resolved_package_ids") or []),
    }


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    e1_script_path = repo_root / "run_showcase_demo_e1.ps1"
    t1_script_path = repo_root / "tools" / "run_t1_evidence_pack.ps1"
    t2_script_path = repo_root / "tools" / "run_t2_workbench.ps1"
    latest_e1_report_path = repo_root / "Saved" / "verification" / "latest_showcase_demo_e1_report.json"
    latest_t1_manifest_path = repo_root / "Saved" / "tooling" / "t1" / "latest" / "manifest.json"

    for path_key, path_value in (
        ("e1_script_path", e1_script_path),
        ("t1_script_path", t1_script_path),
        ("t2_script_path", t2_script_path),
    ):
        if not path_value.exists():
            failed_requirements.append(
                make_failed_requirement(
                    "stability_script_missing",
                    "The E1 stability gate requires all orchestration scripts to exist.",
                    path_key=path_key,
                    path=str(path_value),
                )
            )

    e1_reruns = []
    if not failed_requirements:
        rerun_total = int(FIXED_EXECUTION_PROFILE["rerun_count"])
        for index in range(1, rerun_total + 1):
            step_id = f"e1_rerun_{index:02d}"
            step_root = output_root / step_id
            step_root.mkdir(parents=True, exist_ok=True)
            report_path = step_root / "showcase_demo_e1_report.json"
            if index == rerun_total:
                step_latest_report_path = latest_e1_report_path
            else:
                step_latest_report_path = step_root / "latest_showcase_demo_e1_report.json"
            returncode, stdout, stderr = run_powershell_script(
                e1_script_path,
                [
                    "-WorkspaceConfig",
                    args.workspace_config,
                    "-OutputRoot",
                    str(step_root),
                    "-LatestReportPath",
                    str(step_latest_report_path),
                ],
            )
            result = rerun_result(step_id, report_path, step_latest_report_path, returncode, stdout, stderr)
            e1_reruns.append(result)
            if not report_path.exists():
                failed_requirements.append(
                    make_failed_requirement(
                        "e1_rerun_report_missing",
                        "E1 stability requires each rerun to emit a showcase demo report.",
                        step_id=step_id,
                        expected_report_path=str(report_path.resolve()),
                    )
                )
                break
            if returncode != 0 or result["status"] != "pass":
                failed_requirements.append(
                    make_failed_requirement(
                        "e1_rerun_failed",
                        "E1 stability requires both consecutive E1 reruns to pass.",
                        step_id=step_id,
                        returncode=returncode,
                        report_path=result["report_path"],
                    )
                )
                break

    if len(e1_reruns) == int(FIXED_EXECUTION_PROFILE["rerun_count"]) and not failed_requirements:
        first_signature = e1_reruns[0].get("signature") or {}
        second_signature = e1_reruns[1].get("signature") or {}
        if first_signature != second_signature:
            failed_requirements.append(
                make_failed_requirement(
                    "e1_rerun_signature_mismatch",
                    "E1 stability requires the consecutive reruns to resolve the same packages and showcase counts.",
                    first_signature=first_signature,
                    second_signature=second_signature,
                )
            )

    t1_result = {
        "status": "skipped",
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "manifest_path": str(latest_t1_manifest_path.resolve()),
    }
    t2_result = {
        "status": "skipped",
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "state_path": str((output_root / "t2_dump_state.json").resolve()),
        "state": None,
    }

    if not failed_requirements and bool(FIXED_EXECUTION_PROFILE["refresh_t1_evidence_pack"]):
        returncode, stdout, stderr = run_powershell_script(t1_script_path, [])
        t1_result.update(
            {
                "status": "pass" if returncode == 0 and latest_t1_manifest_path.exists() else "fail",
                "returncode": int(returncode),
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
            }
        )
        if t1_result["status"] != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "t1_evidence_pack_refresh_failed",
                    "E1 stability requires the latest T1 evidence pack to refresh successfully after the reruns.",
                    manifest_path=str(latest_t1_manifest_path.resolve()),
                    returncode=returncode,
                )
            )

    if not failed_requirements and bool(FIXED_EXECUTION_PROFILE["verify_t2_latest_consumption"]):
        returncode, stdout, stderr = run_powershell_script(
            t2_script_path,
            ["-Latest", "-DumpStateJson", "-ExitAfterLoad"],
        )
        t2_state = None
        parse_error = None
        if returncode == 0:
            try:
                t2_state = parse_json_stdout(stdout)
                write_json(Path(t2_result["state_path"]), t2_state)
            except Exception as exc:
                parse_error = str(exc)
        t2_result.update(
            {
                "status": "pass" if returncode == 0 and isinstance(t2_state, dict) else "fail",
                "returncode": int(returncode),
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
                "state": t2_state,
                "parse_error": parse_error,
            }
        )
        if t2_result["status"] != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "t2_latest_consumption_failed",
                    "E1 stability requires T2 to load the latest evidence pack successfully.",
                    returncode=returncode,
                    parse_error=parse_error,
                )
            )
        else:
            active_line = list(((t2_state or {}).get("report_categories") or {}).get("active_line") or [])
            if str(FIXED_EXECUTION_PROFILE["required_t2_status"]) != str((t2_state or {}).get("status") or ""):
                failed_requirements.append(
                    make_failed_requirement(
                        "t2_latest_status_not_pass",
                        "E1 stability requires T2 latest state to be pass.",
                        t2_status=(t2_state or {}).get("status"),
                    )
                )
            if str(FIXED_EXECUTION_PROFILE["required_t2_active_gate_id"]) not in active_line:
                failed_requirements.append(
                    make_failed_requirement(
                        "t2_missing_e1_active_gate",
                        "E1 stability requires T2 to expose showcase_demo_e1 in the active line report list.",
                        active_line=active_line,
                    )
                )

    counts = {
        "required_reruns": int(FIXED_EXECUTION_PROFILE["rerun_count"]),
        "completed_reruns": len(e1_reruns),
        "passing_reruns": sum(1 for item in e1_reruns if item.get("status") == "pass"),
        "t1_refresh_passed": int(t1_result.get("status") == "pass"),
        "t2_consumption_passed": int(t2_result.get("status") == "pass"),
    }
    status = "pass" if not failed_requirements and counts["passing_reruns"] == counts["required_reruns"] else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_e1_stability_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "e1_reruns": e1_reruns,
            "t1_refresh": t1_result,
            "t2_latest_consumption": t2_result,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "latest_e1_report_path": str(latest_e1_report_path.resolve()),
                "latest_t1_manifest_path": str(latest_t1_manifest_path.resolve()),
            },
        },
        "aiue_showcase_demo_e1_stability_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_showcase_demo_e1_stability_report",
            notes=[
                "internal_demo_stability_gate",
                "e1_to_e2_entry_check",
                "t1_t2_consumption_required",
            ],
        ),
    )
    report_path = output_root / "showcase_demo_e1_stability_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    raise SystemExit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
