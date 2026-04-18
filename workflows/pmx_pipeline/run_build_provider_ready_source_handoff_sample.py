from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from aiue_core.schema_utils import write_json  # noqa: E402


AXIS_MAP = {
    0: "x",
    1: "y",
    2: "z",
}

UNIT_SCALE_TO_NAME = {
    1.0: "cm",
    10.0: "mm",
    100.0: "m",
}


def _axis_name(axis_code: int | None) -> str:
    if axis_code is None:
        return ""
    return AXIS_MAP.get(axis_code, "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wrap a raw converted mesh into a provider-ready source handoff sample package.")
    parser.add_argument("--source-zip")
    parser.add_argument("--source-mesh")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--fixture-id", default="bodypaint_trial::lower_body_core_source_v1")
    parser.add_argument("--body-family-id", default="bodypaint_trial")
    parser.add_argument("--fixture-scope", default="lower_body_core")
    parser.add_argument("--source-module-id", action="append", dest="source_module_ids")
    parser.add_argument("--exporter-tool", default="aiue_source_wrap")
    parser.add_argument("--exporter-version", default="0.1")
    parser.add_argument("--fusion-recipe-id", default="")
    parser.add_argument("--rig-profile-id", default="rig_profile::bodypaint_trial::pending")
    parser.add_argument("--material-profile-id", default="material_profile::bodypaint_trial::source_scan_v1")
    parser.add_argument("--mesh-output-name", default="lower_body_core_hi.fbx")
    parser.add_argument("--linear-unit")
    parser.add_argument("--up-axis")
    parser.add_argument("--forward-axis")
    parser.add_argument("--notes", action="append", default=[])
    return parser.parse_args()


def _sanitize_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_")
    return token.lower() or "sample"


def _read_source_mesh(args: argparse.Namespace, staging_root: Path) -> tuple[Path, Path]:
    if args.source_mesh:
        source_mesh = Path(args.source_mesh).expanduser().resolve()
        if not source_mesh.exists():
            raise FileNotFoundError(f"Source mesh does not exist: {source_mesh}")
        staging_root.mkdir(parents=True, exist_ok=True)
        staged_mesh = staging_root / source_mesh.name
        shutil.copy2(source_mesh, staged_mesh)
        return source_mesh, staged_mesh

    if not args.source_zip:
        raise FileNotFoundError("Either --source-zip or --source-mesh is required.")
    source_zip = Path(args.source_zip).expanduser().resolve()
    if not source_zip.exists():
        raise FileNotFoundError(f"Source zip does not exist: {source_zip}")

    staging_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_zip, "r") as archive:
        archive.extractall(staging_root)
    mesh_files = sorted(
        path for path in staging_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".fbx", ".obj", ".usd", ".usda", ".usdc", ".abc"}
    )
    if len(mesh_files) != 1:
        raise RuntimeError(f"Expected exactly one mesh in source zip, found {len(mesh_files)}")
    return source_zip, mesh_files[0]


def _read_fbx_property_int(data: bytes, token: bytes) -> int | None:
    index = data.find(token)
    if index < 0:
        return None
    marker = data.find(b"IntegerS\x00\x00\x00\x00I", index)
    if marker < 0:
        return None
    value_offset = marker + len(b"IntegerS\x00\x00\x00\x00I")
    if value_offset + 4 > len(data):
        return None
    return int(struct.unpack("<i", data[value_offset : value_offset + 4])[0])


def _read_fbx_property_double(data: bytes, token: bytes) -> float | None:
    index = data.find(token)
    if index < 0:
        return None
    marker = data.find(b"NumberS\x00\x00\x00\x00D", index)
    if marker < 0:
        return None
    value_offset = marker + len(b"NumberS\x00\x00\x00\x00D")
    if value_offset + 8 > len(data):
        return None
    return float(struct.unpack("<d", data[value_offset : value_offset + 8])[0])


def inspect_fbx_header_hints(mesh_path: Path) -> dict[str, object]:
    if mesh_path.suffix.lower() != ".fbx":
        return {}
    data = mesh_path.read_bytes()
    up_axis_code = _read_fbx_property_int(data, b"UpAxis")
    front_axis_code = _read_fbx_property_int(data, b"FrontAxis")
    coord_axis_code = _read_fbx_property_int(data, b"CoordAxis")
    unit_scale_factor = _read_fbx_property_double(data, b"UnitScaleFactor")
    return {
        "up_axis_code": up_axis_code,
        "front_axis_code": front_axis_code,
        "coord_axis_code": coord_axis_code,
        "unit_scale_factor": unit_scale_factor,
        "up_axis": _axis_name(up_axis_code),
        "forward_axis": _axis_name(front_axis_code),
        "coord_axis": _axis_name(coord_axis_code),
        "linear_unit": UNIT_SCALE_TO_NAME.get(round(unit_scale_factor or 0.0, 4), ""),
    }


def build_manifest(args: argparse.Namespace, *, mesh_output_name: str, header_hints: dict[str, object], source_input_path: Path) -> dict[str, object]:
    fusion_recipe_id = args.fusion_recipe_id or f"aiue_source_wrap::{args.fixture_id}::v1"
    source_module_ids = list(args.source_module_ids or [f"{args.body_family_id}/raw/{_sanitize_token(source_input_path.stem)}"])
    linear_unit = args.linear_unit or str(header_hints.get("linear_unit") or "")
    up_axis = args.up_axis or str(header_hints.get("up_axis") or "")
    forward_axis = args.forward_axis or str(header_hints.get("forward_axis") or "")
    notes = list(args.notes or [])
    notes.extend(
        [
            "provider-ready source handoff sample",
            "prepared for BodyPaint upstream intake, not yet the strict UE-facing C2 artifact",
        ]
    )
    return {
        "fixture_id": args.fixture_id,
        "body_family_id": args.body_family_id,
        "fixture_scope": args.fixture_scope,
        "source_module_ids": source_module_ids,
        "primary_mesh_relative_path": f"meshes/{mesh_output_name}",
        "mesh_format": Path(mesh_output_name).suffix.lower().lstrip("."),
        "material_bundle_relative_root": "materials",
        "texture_relative_paths": [],
        "fusion_recipe_id": fusion_recipe_id,
        "rig_profile_id": args.rig_profile_id,
        "material_profile_id": args.material_profile_id,
        "exporter": {
            "tool": args.exporter_tool,
            "version": args.exporter_version,
        },
        "coordinate_system": {
            "linear_unit": linear_unit,
            "up_axis": up_axis,
            "forward_axis": forward_axis,
        },
        "quality": {
            "topology_state": "source_converted_candidate",
            "uv_state": "source_preserved_unknown",
            "watertight_expected": False,
            "runtime_ready": False,
        },
        "source_observation": {
            "source_input_path": str(source_input_path),
            "header_hints": header_hints,
        },
        "notes": notes,
    }


def zip_directory(source_root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_root.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=str(path.relative_to(source_root)).replace("\\", "/"))


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root).expanduser().resolve()
    staging_root = output_root / "staging_source"
    package_root = output_root / "provider_ready_source_handoff"
    meshes_root = package_root / "meshes"
    materials_root = package_root / "materials"
    output_root.mkdir(parents=True, exist_ok=True)
    source_input_path, staged_mesh = _read_source_mesh(args, staging_root)

    header_hints = inspect_fbx_header_hints(staged_mesh)
    mesh_output_name = args.mesh_output_name
    if staged_mesh.suffix.lower() and not mesh_output_name.lower().endswith(staged_mesh.suffix.lower()):
        mesh_output_name = Path(mesh_output_name).stem + staged_mesh.suffix.lower()

    if package_root.exists():
        shutil.rmtree(package_root)
    meshes_root.mkdir(parents=True, exist_ok=True)
    materials_root.mkdir(parents=True, exist_ok=True)
    packaged_mesh_path = meshes_root / mesh_output_name
    shutil.copy2(staged_mesh, packaged_mesh_path)

    manifest = build_manifest(
        args,
        mesh_output_name=mesh_output_name,
        header_hints=header_hints,
        source_input_path=source_input_path,
    )
    manifest_path = package_root / "canonical_fusion_fixture_manifest.json"
    write_json(manifest_path, manifest)

    zip_path = output_root / f"{_sanitize_token(args.fixture_id)}.zip"
    zip_directory(package_root, zip_path)

    summary = {
        "status": "pass",
        "source_input_path": str(source_input_path),
        "packaged_mesh_path": str(packaged_mesh_path),
        "manifest_path": str(manifest_path),
        "zip_path": str(zip_path),
        "header_hints": header_hints,
    }
    write_json(output_root / "build_provider_ready_source_handoff_summary.json", summary)
    print(f"Provider-ready source handoff sample written to: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
