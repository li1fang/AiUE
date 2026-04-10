from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime.capture import capture_frame, ensure_stage_anchors, inspect_stage_anchors, load_level, run_scene_sweep, spawn_host
from runtime.composition import build_equipment_registry, import_package, import_package_dry_run
from runtime.inspection import debug_physics_api, inspect_host, inspect_host_visual, list_assets
from runtime.preview import action_preview, animation_preview
from runtime.retarget import retarget_author_chains, retarget_bootstrap, retarget_preflight


def dispatch(request: dict) -> dict:
    command = request["command"]
    if command == "inspect-host":
        return inspect_host(request)
    if command == "inspect-host-visual":
        return inspect_host_visual(request)
    if command == "action-preview":
        return action_preview(request)
    if command == "animation-preview":
        return animation_preview(request)
    if command == "retarget-preflight":
        return retarget_preflight(request)
    if command == "retarget-bootstrap":
        return retarget_bootstrap(request)
    if command == "retarget-author-chains":
        return retarget_author_chains(request)
    if command == "debug-physics-api":
        return debug_physics_api(request)
    if command == "load-level":
        return load_level(request)
    if command == "spawn-host":
        return spawn_host(request)
    if command == "inspect-stage-anchors":
        return inspect_stage_anchors(request)
    if command == "ensure-stage-anchors":
        return ensure_stage_anchors(request)
    if command == "capture-frame":
        return capture_frame(request)
    if command == "stage-capture":
        stage_request = dict(request)
        stage_request["command"] = "capture-frame"
        return capture_frame(stage_request)
    if command == "run-scene-sweep":
        return run_scene_sweep(request)
    if command == "list-assets":
        return list_assets(request)
    if command == "build-equipment-registry":
        return build_equipment_registry(request)
    if command == "import-package" and request.get("dry_run"):
        return import_package_dry_run(request)
    if command == "import-package":
        return import_package(request)
    return {
        "warnings": [],
        "errors": [f"unsupported_command:{command}"],
    }


def main() -> int:
    if len(sys.argv) >= 3:
        request_path = Path(sys.argv[1]).expanduser().resolve()
        response_path = Path(sys.argv[2]).expanduser().resolve()
    else:
        request_env = os.environ.get("AIUE_REQUEST_PATH")
        response_env = os.environ.get("AIUE_RESPONSE_PATH")
        if not request_env or not response_env:
            raise RuntimeError("AIUE_REQUEST_PATH and AIUE_RESPONSE_PATH must be provided")
        request_path = Path(request_env).expanduser().resolve()
        response_path = Path(response_env).expanduser().resolve()
    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    try:
        result = dispatch(request)
        payload = {
            "success": not result.get("errors"),
            "result": result,
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
        }
    except Exception as exc:
        payload = {
            "success": False,
            "result": {},
            "warnings": [],
            "errors": [str(exc), traceback.format_exc()],
        }
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
