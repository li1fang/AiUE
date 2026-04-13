from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from aiue_unreal.execution_errors import ActionResultError

from ._delegate import delegate_to_host_command


def _load_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8-sig"))


def _resolve_manifest_artifact(manifest_path: Path, artifact_path: str | None) -> Path | None:
    if not artifact_path:
        return None
    candidate = Path(str(artifact_path)).expanduser()
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    return (manifest_path.parent / candidate).resolve(strict=False)


def _resolve_blender_exe(workspace: dict) -> Path | None:
    paths = workspace.get("paths") or {}
    candidates = []
    for raw in (
        paths.get("blender_exe"),
        os.environ.get("AIUE_BLENDER_EXE"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "blender-launcher.exe",
    ):
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if candidate.exists():
            return candidate.resolve()
    return None


def _prepare_motion_import_source(context: dict, params: dict) -> tuple[Path, dict]:
    manifest_path = Path(str(params.get("manifest") or params.get("manifest_path") or "")).expanduser().resolve()
    if not manifest_path.exists():
        raise ActionResultError(
            "motion_manifest_missing",
            result={"errors": [f"motion_manifest_missing:{manifest_path}"], "warnings": []},
            errors=[f"motion_manifest_missing:{manifest_path}"],
        )

    manifest = _load_manifest(manifest_path)
    export_artifacts = manifest.get("export_artifacts") or {}
    source_path = _resolve_manifest_artifact(manifest_path, export_artifacts.get("motion_fbx"))
    if source_path and source_path.exists():
        return source_path, {"status": "pass", "conversion": "not_needed", "source_path": str(source_path)}

    source_path = _resolve_manifest_artifact(manifest_path, export_artifacts.get("motion_bvh") or "motion.bvh")
    if source_path is None or not source_path.exists():
        raise ActionResultError(
            "motion_bvh_missing",
            result={"errors": [f"motion_bvh_missing:{source_path or 'missing'}"], "warnings": []},
            errors=[f"motion_bvh_missing:{source_path or 'missing'}"],
        )
    if source_path.suffix.lower() != ".bvh":
        return source_path, {"status": "pass", "conversion": "not_needed", "source_path": str(source_path)}

    blender_exe = _resolve_blender_exe(context["workspace"])
    if blender_exe is None:
        raise ActionResultError(
            "motion_bvh_conversion_blender_missing",
            result={
                "errors": ["motion_bvh_conversion_blender_missing"],
                "warnings": [],
                "motion_source_path": str(source_path),
            },
            errors=["motion_bvh_conversion_blender_missing"],
        )

    package_id = str(manifest.get("package_id") or "motion_package")
    prepared_root = Path(str(context["output_path"])).expanduser().resolve().parent / "prepared_motion"
    prepared_root.mkdir(parents=True, exist_ok=True)
    output_fbx = prepared_root / f"AN_{package_id}.fbx"
    report_path = prepared_root / f"AN_{package_id}.conversion_report.json"
    script_path = Path(__file__).resolve().parent / "scripts" / "convert_bvh_to_fbx_blender.py"
    command = [
        str(blender_exe),
        "-b",
        "--factory-startup",
        "--python",
        str(script_path),
        "--",
        "--input",
        str(source_path),
        "--output",
        str(output_fbx),
        "--report",
        str(report_path),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    conversion_payload = {
        "status": "pass" if completed.returncode == 0 and output_fbx.exists() else "fail",
        "conversion": "bvh_to_fbx_blender",
        "source_path": str(source_path),
        "output_path": str(output_fbx),
        "report_path": str(report_path),
        "blender_exe": str(blender_exe),
        "returncode": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0 or not output_fbx.exists():
        raise ActionResultError(
            "motion_bvh_conversion_failed",
            result={
                "errors": ["motion_bvh_conversion_failed"],
                "warnings": [],
                "motion_source_path": str(source_path),
                "motion_conversion": conversion_payload,
            },
            errors=["motion_bvh_conversion_failed"],
        )
    return output_fbx, conversion_payload


def run(context: dict, params: dict) -> dict:
    prepared_params = dict(params)
    motion_import_source_path, conversion_payload = _prepare_motion_import_source(context, prepared_params)
    prepared_params["motion_import_source_path"] = str(motion_import_source_path)
    try:
        result = delegate_to_host_command(context, "import-motion-packet", prepared_params)
    except ActionResultError as exc:
        exc.result["motion_conversion"] = conversion_payload
        raise
    result["motion_conversion"] = conversion_payload
    result["motion_import_source_path"] = str(motion_import_source_path)
    return result
