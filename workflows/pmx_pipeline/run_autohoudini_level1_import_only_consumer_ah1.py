from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import (  # noqa: E402
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
    repo_root_from_workspace,
    write_report_pair,
)
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_workspace_config, write_json  # noqa: E402
from aiue_unreal.action_runner import run_action  # noqa: E402
from autohoudini_level1 import (  # noqa: E402
    REQUEST_OPERATION,
    SUPPORTED_IMPORT_MODE,
    build_external_result,
    build_import_summary,
    load_level1_request,
    resolve_request_json_path,
)


GATE_ID = "autohoudini_level1_import_only_consumer_ah1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE AH1 AutoHoudini Level1 import-only consumer.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--request-json")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = None
    if latest_report_path.exists():
        try:
            import json

            previous_report = json.loads(latest_report_path.read_text(encoding="utf-8-sig"))
        except Exception:
            previous_report = None

    failed_requirements: list[dict] = []
    request_payload: dict = {}
    request_json_path: Path | None = None
    try:
        request_json_path = resolve_request_json_path(workspace, args.request_json)
        request_payload = load_level1_request(request_json_path)
    except Exception as exc:
        failed_requirements.append(
            make_failed_requirement(
                "ah1_request_unresolved",
                "AH1 could not resolve a valid AutoHoudini Level1 request JSON.",
                error=str(exc),
            )
        )

    import_action_payload = {
        "status": "fail",
        "success": False,
        "warnings": [],
        "errors": [],
        "result": {},
    }
    import_action_result_path = ""
    mirrored_result_path = output_root / "autohoudini_aiue_level1_consumer_result_v0.json"
    mirrored_result = {}
    if not failed_requirements and request_json_path is not None:
        import_action_payload, import_action_result_path = run_action(
            {
                "command": "import-level1-curve-bundle",
                "mode": "cmd_nullrhi",
                "params": {
                    "request_json": str(request_json_path),
                },
                "output_path": str((output_root / "import_level1_curve_bundle.action.json").resolve()),
            },
            workspace,
        )
        host_result = dict(import_action_payload.get("result") or {})
        import_summary = build_import_summary(import_action_payload)
        if str(import_action_payload.get("status") or "") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "ah1_import_action_failed",
                    "AH1 import action did not pass.",
                    action_status=str(import_action_payload.get("status") or ""),
                )
            )
        if str(host_result.get("status") or "") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "ah1_host_import_failed",
                    "Host-side Level1 curve import did not pass.",
                    host_status=str(host_result.get("status") or ""),
                )
            )
        if str(host_result.get("resolved_import_mode") or "") != SUPPORTED_IMPORT_MODE:
            failed_requirements.append(
                make_failed_requirement(
                    "ah1_resolved_import_mode_invalid",
                    "AH1 only supports curve_float_asset_set import mode.",
                    resolved_import_mode=str(host_result.get("resolved_import_mode") or ""),
                )
            )
        if int(import_summary.get("imported_asset_count") or 0) != int(import_summary.get("channel_count") or 0):
            failed_requirements.append(
                make_failed_requirement(
                    "ah1_imported_asset_count_mismatch",
                    "Imported asset count did not match the declared channel count.",
                    imported_asset_count=int(import_summary.get("imported_asset_count") or 0),
                    channel_count=int(import_summary.get("channel_count") or 0),
                )
            )
        mirrored_result = build_external_result(
            import_action_payload=import_action_payload,
            import_action_result_path=import_action_result_path,
            request_payload=request_payload,
            request_json_path=request_json_path,
            workspace_config_path=Path(args.workspace_config).expanduser().resolve(),
            combined_result_path=mirrored_result_path,
            host_key=str(host_result.get("host_key") or ""),
        )
        write_json(mirrored_result_path, mirrored_result)

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "ah1_import_only_consumer_first_pass",
    )
    host_result = dict(import_action_payload.get("result") or {})
    import_summary = build_import_summary(import_action_payload)
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "fixed_execution_profile": {
                "operation": REQUEST_OPERATION,
                "mode": "import_only",
                "supported_unreal_import_mode": SUPPORTED_IMPORT_MODE,
                "preview_supported": False,
                "mirrored_external_result": True,
            },
            "request_json_path": str(request_json_path) if request_json_path else "",
            "request_snapshot": {
                "target_package_id": str(request_payload.get("target_package_id") or ""),
                "curve_asset_root": str(request_payload.get("curve_asset_root") or ""),
                "requested_unreal_import_mode": str(request_payload.get("unreal_import_mode") or ""),
                "host_key": str(request_payload.get("host_key") or ""),
            },
            "counts": {
                "channel_count": int(import_summary.get("channel_count") or 0),
                "imported_asset_count": int(import_summary.get("imported_asset_count") or 0),
                "warning_count": len(list(import_summary.get("warnings") or [])),
                "error_count": len(list(import_summary.get("errors") or [])),
            },
            "import_action": {
                "status": str(import_action_payload.get("status") or ""),
                "success": bool(import_action_payload.get("success")),
                "output_path": import_action_result_path,
            },
            "host_result": host_result,
            "mirrored_external_result": mirrored_result,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "import_action_result_path": import_action_result_path,
                "mirrored_external_result_path": str(mirrored_result_path.resolve()) if mirrored_result else "",
            },
        },
        "autohoudini_level1_import_only_consumer_ah1_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="autohoudini_level1_import_only_consumer_ah1_report",
            notes=["internal_gate_runner", "autohoudini_level1", "import_only_consumer"],
        ),
    )
    report_path = output_root / "autohoudini_level1_import_only_consumer_ah1_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"AH1 AutoHoudini Level1 import-only consumer report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
