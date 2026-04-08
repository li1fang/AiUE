from __future__ import annotations

import argparse
import json

from _bootstrap import ensure_aiue_paths

ensure_aiue_paths()

from aiue_core.schema_utils import load_workspace_config
from aiue_unreal.action_runner import run_action


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE PMX scene-sweep workflow.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--package-id")
    parser.add_argument("--mode", default="editor_rendered")
    parser.add_argument("--enable-capture", action="store_true")
    parser.add_argument("--capture-root")
    parser.add_argument("--suite-output")
    parser.add_argument("--capture-manifest-output")
    parser.add_argument("--capture-delay-seconds", type=float)
    parser.add_argument("--camera-lifecycle", choices=["reuse_camera", "respawn_camera_per_scenario"])
    parser.add_argument("--level-lifecycle", choices=["reuse_level", "reload_level_per_run"])
    parser.add_argument("--scenario-scheduling", choices=["single_scenario", "batched_scenarios"])
    parser.add_argument("--scenario-names", nargs="*")
    parser.add_argument("--completion-strategy")
    parser.add_argument("--settle-timeout-seconds", type=float)
    parser.add_argument("--file-stability-window-seconds", type=float)
    parser.add_argument("--viewport-pump-interval-seconds", type=float)
    parser.add_argument("--quit-barrier-seconds", type=float)
    parser.add_argument("--post-exit-finalize-wait-seconds", type=int)
    parser.add_argument("--output-path")
    return parser.parse_args()


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    payload, output_path = run_action(
        {
            "command": "run-scene-sweep",
            "mode": args.mode,
            "params": {
                "summary": args.summary,
                "package_id": args.package_id,
                "enable_capture": args.enable_capture,
                "capture_root": args.capture_root,
                "suite_output": args.suite_output,
                "capture_manifest_output": args.capture_manifest_output,
                "capture_delay_seconds": args.capture_delay_seconds,
                "camera_lifecycle": args.camera_lifecycle,
                "level_lifecycle": args.level_lifecycle,
                "scenario_scheduling": args.scenario_scheduling,
                "scenario_names": args.scenario_names,
                "completion_strategy": args.completion_strategy,
                "settle_timeout_seconds": args.settle_timeout_seconds,
                "file_stability_window_seconds": args.file_stability_window_seconds,
                "viewport_pump_interval_seconds": args.viewport_pump_interval_seconds,
                "quit_barrier_seconds": args.quit_barrier_seconds,
                "post_exit_finalize_wait_seconds": args.post_exit_finalize_wait_seconds
            },
            "output_path": args.output_path
        },
        workspace
    )
    print(json.dumps({"output_path": output_path, "status": payload["status"]}, ensure_ascii=False))
    if not payload.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
