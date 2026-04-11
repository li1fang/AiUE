from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from aiue_core.schema_utils import load_json, write_json
from aiue_t1.evidence_pack import build_evidence_pack


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures"
REPORT_FIXTURES = FIXTURE_ROOT / "reports"
WORKBENCH_SCRIPT = REPO_ROOT / "tools" / "run_t2_workbench.ps1"
DEMO_REQUEST_SCRIPT = REPO_ROOT / "tools" / "run_e2_demo_request.ps1"
DEFAULT_E2_SESSION_NAME = "playable_demo_e2_session.json"


def materialize_report_fixtures(target_root: Path) -> Path:
    target_root.mkdir(parents=True, exist_ok=True)
    placeholder_root = str(FIXTURE_ROOT).replace("\\", "/")
    for report_path in REPORT_FIXTURES.glob("*.json"):
        payload = load_json(report_path)
        serialized = json.dumps(payload)
        serialized = serialized.replace("__FIXTURE_ROOT__", placeholder_root)
        write_json(target_root / report_path.name, json.loads(serialized))
    return target_root


def build_fixture_pack(tmp_path: Path) -> dict:
    verification_root = materialize_report_fixtures(tmp_path / "verification")
    output_root = tmp_path / "tooling" / "pack"
    latest_root = tmp_path / "tooling" / "latest"
    manifest = build_evidence_pack(
        verification_root=verification_root,
        output_root=output_root,
        latest_root=latest_root,
        repo_root=tmp_path,
    )
    session_manifest_path = build_fixture_e2_session(tmp_path)
    return {
        "manifest_path": output_root / "manifest.json",
        "output_root": output_root,
        "latest_root": latest_root,
        "manifest": manifest,
        "session_manifest_path": session_manifest_path,
    }


def build_fixture_e2_session(tmp_path: Path) -> Path:
    session_root = tmp_path / "Saved" / "demo" / "e2" / "latest"
    session_root.mkdir(parents=True, exist_ok=True)
    session_manifest_path = session_root / DEFAULT_E2_SESSION_NAME
    session_payload = {
        "generated_at_utc": "2026-04-11T05:35:30+00:00",
        "session_id": "playable_demo_e2_bootstrap",
        "session_type": "playable_demo_bootstrap",
        "host_key": "demo",
        "mode": "editor_rendered",
        "level_path": "/Game/Levels/DefaultLevel",
        "default_package_id": "pkg_alpha",
        "switch_order": ["pkg_alpha"],
        "packages": [
            {
                "package_id": "pkg_alpha",
                "sample_id": "fixture_alpha",
                "host_blueprint_asset": "/Game/Fixture/BP_PMXCharacterHost_FixtureAlpha",
                "level_path": "/Game/Levels/DefaultLevel",
                "spawn_location": {"x": 0.0, "y": 0.0, "z": 120.0},
                "spawn_rotation": {"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
                "hero_shot_id": "top",
                "hero_shot_plan": {
                    "shot_id": "top",
                    "camera_id": "top",
                    "camera_source": "explicit_pose",
                    "camera_location": {"x": 92.0, "y": -82.0, "z": 620.0},
                    "camera_rotation": {"pitch": -72.0, "yaw": 138.0, "roll": 0.0},
                    "target_location": {"x": 0.0, "y": 0.0, "z": 240.0},
                },
                "slot_bindings": [
                    {"slot_name": "weapon", "item_kind": "skeletal_mesh"},
                    {"slot_name": "clothing", "item_kind": "skeletal_mesh"},
                    {"slot_name": "fx", "item_kind": "niagara_system"},
                ],
                "clothing_binding": {
                    "slot_name": "clothing",
                    "item_package_id": "fixture_hair",
                    "item_kind": "skeletal_mesh",
                    "attach_socket_name": "Head",
                    "skeletal_mesh_asset": "/Game/Characters/Echo/Meshes/SKM_Echo_Hair.SKM_Echo_Hair",
                },
                "fx_binding": {
                    "slot_name": "fx",
                    "item_package_id": "fixture_fx",
                    "item_kind": "niagara_system",
                    "attach_socket_name": "WeaponSocket",
                    "niagara_system_asset": "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst.DirectionalBurst",
                    "niagara_desired_age_seconds": 0.08,
                    "niagara_seek_delta_seconds": 0.0166667,
                    "niagara_advance_step_count": 4,
                    "niagara_advance_step_delta_seconds": 0.0166667,
                },
                "action_presets": [
                    {
                        "preset_id": "showcase_root_translate_and_turn",
                        "action_kind": "root_translate_and_turn",
                        "action_distance": 85.0,
                        "action_yaw_delta": 24.0,
                        "action_settle_seconds": 0.2,
                        "status": "pass",
                    }
                ],
                "animation_presets": [
                    {
                        "preset_id": "MM_Attack_01",
                        "family": "attack",
                        "source_gate_id": "demo_retargeted_animation_preview_d8",
                        "requested_animation_asset_path": "/Game/CombatMagicAnims/MM_Attack_01",
                        "resolved_animation_asset_path": "/Game/RTG_MM_Attack_01_PMXPreview",
                        "status": "pass",
                    }
                ],
                "evidence": {
                    "hero_before_image_path": str((FIXTURE_ROOT / "images" / "front.ppm").resolve()),
                    "hero_after_image_path": str((FIXTURE_ROOT / "images" / "side.ppm").resolve()),
                },
            }
        ],
        "source_reports": {
            "e1_report_path": str((REPORT_FIXTURES / "latest_demo_cross_bundle_regression_d12_report.json").resolve()),
        },
    }
    write_json(session_manifest_path, session_payload)
    return session_manifest_path


def create_invalid_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "invalid_manifest.json"
    path.write_text("{ invalid json", encoding="utf-8")
    return path


def create_missing_artifact_manifest(tmp_path: Path) -> Path:
    pack = build_fixture_pack(tmp_path)
    preview_images = list(pack["manifest"]["artifacts"]["preview_images"])
    missing_relative_path = preview_images[0]["relative_path"]
    missing_path = pack["output_root"] / Path(missing_relative_path)
    if missing_path.exists():
        missing_path.unlink()
    return pack["manifest_path"]


def parse_json_from_stdout(stdout: str) -> dict:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        raise AssertionError(f"Could not locate JSON payload in stdout:\n{stdout}")
    return json.loads(stdout[start : end + 1])


def run_workbench_process(
    *,
    manifest_path: Path | None = None,
    latest: bool = False,
    session_manifest_path: Path | None = None,
    workspace_config_path: Path | None = None,
    demo_request_export: bool = False,
    demo_request_dry_run: bool = False,
    demo_request_invoke: bool = False,
    demo_request_kind: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(WORKBENCH_SCRIPT),
        "-DumpStateJson",
        "-ExitAfterLoad",
    ]
    if manifest_path is not None:
        command += ["-Manifest", str(manifest_path)]
    elif latest:
        command += ["-Latest"]
    if session_manifest_path is not None:
        command += ["-SessionManifest", str(session_manifest_path)]
    if workspace_config_path is not None:
        command += ["-WorkspaceConfig", str(workspace_config_path)]
    if demo_request_export:
        command += ["-DemoRequestExport"]
    if demo_request_dry_run:
        command += ["-DemoRequestDryRun"]
    if demo_request_invoke:
        command += ["-DemoRequestInvoke"]
    if demo_request_kind is not None:
        command += ["-DemoRequestKind", str(demo_request_kind)]
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_API"] = "pyside6"
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    payload = parse_json_from_stdout(completed.stdout)
    return completed, payload


def run_demo_request_process(
    *,
    manifest_path: Path,
    session_manifest_path: Path | None = None,
    request_kind: str = "action_preview",
    package_id: str | None = None,
    dump_request_json: bool = True,
    write_request_path: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(DEMO_REQUEST_SCRIPT),
        "-Manifest",
        str(manifest_path),
        "-RequestKind",
        request_kind,
    ]
    if session_manifest_path is not None:
        command += ["-SessionManifest", str(session_manifest_path)]
    if package_id is not None:
        command += ["-PackageId", str(package_id)]
    if dump_request_json:
        command += ["-DumpRequestJson"]
    if write_request_path is not None:
        command += ["-WriteRequestPath", str(write_request_path)]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    payload = parse_json_from_stdout(completed.stdout)
    return completed, payload
