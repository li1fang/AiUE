from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SUPPORTED_MESH_EXTENSIONS = {
    ".abc",
    ".fbx",
    ".glb",
    ".gltf",
    ".obj",
    ".pmd",
    ".pmx",
}

IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".venv-tooling",
    "__pycache__",
    "binaries",
    "build",
    "dist",
    "intermediate",
    "node_modules",
    "saved",
}

HEAD_ASCII_KEYWORDS = {"face", "head", "skull"}
HEAD_CJK_KEYWORDS = ("人头", "头部", "头模", "脸")
HAIR_ASCII_KEYWORDS = {"bangs", "hair", "ponytail", "fringe", "braid", "bun"}
HAIR_CJK_KEYWORDS = ("头发", "发型", "前发", "后发", "刘海", "髮", "发")
BUST_ASCII_KEYWORDS = {"bust", "boob", "boobs", "breast", "breasts", "chest"}
BUST_CJK_KEYWORDS = ("胸", "乳", "胸部")
LEG_ASCII_KEYWORDS = {"calf", "foot", "knee", "leg", "legs", "shin", "thigh"}
LEG_CJK_KEYWORDS = ("大腿", "小腿", "腿", "膝")
CORE_ASCII_KEYWORDS = {
    "abdomen",
    "arm",
    "arms",
    "body",
    "clavicle",
    "core",
    "hip",
    "hips",
    "pelvis",
    "shoulder",
    "torso",
    "trunk",
    "upperbody",
    "waist",
}
CORE_CJK_KEYWORDS = ("上半身", "手臂", "核心", "肩", "腰", "臀", "躯干")
RAW_ASCII_KEYWORDS = {"highpoly", "hires", "photogrammetry", "raw", "scan", "sculpt", "source", "ztl"}
RAW_CJK_KEYWORDS = ("扫描", "原始", "高模", "源文件", "雕刻")

REQUIRED_BODY_AXES = ("head", "bust_variant", "leg_profile", "core_torso_arm")
OPTIONAL_BODY_AXES = ("hair",)


def _tokenize(text: str) -> tuple[str, set[str]]:
    normalized = text.replace("\\", "/").lower()
    tokens = {token for token in re.split(r"[^a-z0-9]+", normalized) if token}
    return normalized, tokens


def _matches(raw_text: str, tokens: set[str], ascii_keywords: set[str], cjk_keywords: tuple[str, ...]) -> bool:
    if any(keyword in tokens for keyword in ascii_keywords):
        return True
    return any(keyword in raw_text for keyword in cjk_keywords)


def classify_module_kind(relative_path: str | Path) -> str:
    raw_text, tokens = _tokenize(str(relative_path))
    if _matches(raw_text, tokens, HAIR_ASCII_KEYWORDS, HAIR_CJK_KEYWORDS):
        return "hair"
    if _matches(raw_text, tokens, HEAD_ASCII_KEYWORDS, HEAD_CJK_KEYWORDS):
        return "head"
    if _matches(raw_text, tokens, BUST_ASCII_KEYWORDS, BUST_CJK_KEYWORDS):
        return "bust_variant"
    if _matches(raw_text, tokens, LEG_ASCII_KEYWORDS, LEG_CJK_KEYWORDS):
        return "leg_profile"
    if _matches(raw_text, tokens, CORE_ASCII_KEYWORDS, CORE_CJK_KEYWORDS):
        return "core_torso_arm"
    if _matches(raw_text, tokens, RAW_ASCII_KEYWORDS, RAW_CJK_KEYWORDS):
        return "non_consumable_raw_scan"
    return "unknown"


def _is_mesh_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_MESH_EXTENSIONS


def _iter_mesh_files(source_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in source_root.rglob("*"):
        if any(part.lower() in IGNORED_DIR_NAMES for part in path.parts):
            continue
        if _is_mesh_file(path):
            files.append(path)
    files.sort()
    return files


def _family_id_from_relative_path(relative_path: Path) -> str:
    if relative_path.parts[:-1]:
        return str(relative_path.parts[0])
    return "__root__"


def _module_id_from_relative_path(relative_path: Path) -> str:
    return str(relative_path.with_suffix("")).replace("\\", "/")


def _axis_presence(module_kind_counts: dict[str, int]) -> tuple[dict[str, bool], dict[str, bool]]:
    required_presence = {axis: int(module_kind_counts.get(axis) or 0) > 0 for axis in REQUIRED_BODY_AXES}
    optional_presence = {axis: int(module_kind_counts.get(axis) or 0) > 0 for axis in OPTIONAL_BODY_AXES}
    return required_presence, optional_presence


def _family_sort_key(family: dict[str, Any]) -> tuple[int, int, int, int, str]:
    required_presence = dict(family.get("required_axes_present") or {})
    optional_presence = dict(family.get("optional_axes_present") or {})
    return (
        -sum(1 for value in required_presence.values() if value),
        -sum(1 for value in optional_presence.values() if value),
        -int(family.get("module_count") or 0),
        -int(family.get("classified_module_count") or 0),
        str(family.get("family_id") or ""),
    )


def build_modular_morphology_inventory(source_root: str | Path) -> dict[str, Any]:
    resolved_source_root = Path(source_root).expanduser().resolve()
    mesh_files = _iter_mesh_files(resolved_source_root) if resolved_source_root.exists() else []
    module_kind_counts: dict[str, int] = {}
    extension_counts: dict[str, int] = {}
    module_examples_by_kind: dict[str, list[str]] = {}
    families_by_id: dict[str, dict[str, Any]] = {}

    for mesh_path in mesh_files:
        relative_path = mesh_path.relative_to(resolved_source_root)
        module_kind = classify_module_kind(relative_path)
        module_kind_counts[module_kind] = int(module_kind_counts.get(module_kind) or 0) + 1
        extension_counts[mesh_path.suffix.lower()] = int(extension_counts.get(mesh_path.suffix.lower()) or 0) + 1
        module_examples_by_kind.setdefault(module_kind, [])
        if len(module_examples_by_kind[module_kind]) < 5:
            module_examples_by_kind[module_kind].append(str(relative_path).replace("\\", "/"))

        family_id = _family_id_from_relative_path(relative_path)
        family = families_by_id.setdefault(
            family_id,
            {
                "family_id": family_id,
                "family_root": str((resolved_source_root / family_id).resolve()) if family_id != "__root__" else str(resolved_source_root),
                "module_count": 0,
                "classified_module_count": 0,
                "unknown_module_count": 0,
                "module_kind_counts": {},
                "module_ids_by_kind": {},
                "representative_modules": [],
            },
        )
        family["module_count"] = int(family.get("module_count") or 0) + 1
        family["module_kind_counts"][module_kind] = int(family["module_kind_counts"].get(module_kind) or 0) + 1
        family["module_ids_by_kind"].setdefault(module_kind, [])
        family["module_ids_by_kind"][module_kind].append(_module_id_from_relative_path(relative_path))
        if module_kind == "unknown":
            family["unknown_module_count"] = int(family.get("unknown_module_count") or 0) + 1
        else:
            family["classified_module_count"] = int(family.get("classified_module_count") or 0) + 1
        representative_modules = list(family.get("representative_modules") or [])
        if len(representative_modules) < 8:
            representative_modules.append(
                {
                    "module_id": _module_id_from_relative_path(relative_path),
                    "module_kind": module_kind,
                    "relative_path": str(relative_path).replace("\\", "/"),
                }
            )
            family["representative_modules"] = representative_modules

    family_rows: list[dict[str, Any]] = []
    for family in families_by_id.values():
        required_presence, optional_presence = _axis_presence(dict(family.get("module_kind_counts") or {}))
        module_ids_by_kind = {
            str(kind): sorted(str(module_id) for module_id in list(module_ids or []) if str(module_id))
            for kind, module_ids in dict(family.get("module_ids_by_kind") or {}).items()
        }
        family_rows.append(
            {
                **family,
                "module_ids_by_kind": module_ids_by_kind,
                "required_axes_present": required_presence,
                "optional_axes_present": optional_presence,
                "candidate_fixture_family": all(required_presence.values()),
            }
        )

    family_rows.sort(key=_family_sort_key)
    candidate_fixture_families = [family for family in family_rows if bool(family.get("candidate_fixture_family"))]
    canonical_fixture_family_id = str(candidate_fixture_families[0].get("family_id") or "") if candidate_fixture_families else ""

    module_count = len(mesh_files)
    classified_module_count = module_count - int(module_kind_counts.get("unknown") or 0)
    return {
        "source_root": str(resolved_source_root),
        "selection_policy": {
            "required_axes": list(REQUIRED_BODY_AXES),
            "optional_axes": list(OPTIONAL_BODY_AXES),
            "canonical_fixture_rule": "first_candidate_by_required_axes_then_optional_axes_then_module_count",
        },
        "counts": {
            "module_count": module_count,
            "classified_module_count": classified_module_count,
            "unknown_module_count": int(module_kind_counts.get("unknown") or 0),
            "family_count": len(family_rows),
            "candidate_fixture_family_count": len(candidate_fixture_families),
        },
        "module_kind_counts": module_kind_counts,
        "source_extension_counts": extension_counts,
        "module_examples_by_kind": module_examples_by_kind,
        "canonical_fixture_family_id": canonical_fixture_family_id,
        "candidate_fixture_family_ids": [str(item.get("family_id") or "") for item in candidate_fixture_families],
        "per_family_results": family_rows,
    }


def build_body_platform_quality_summary(report_index: dict[str, Any]) -> dict[str, Any]:
    reports_by_gate_id = dict(report_index.get("reports_by_gate_id") or {})
    c1_entry = dict(reports_by_gate_id.get("parametric_body_contract_c1") or {})
    c1_report = dict(c1_entry.get("report") or {})
    c0_entry = dict(reports_by_gate_id.get("modular_morphology_inventory_c0") or {})
    c0_report = dict(c0_entry.get("report") or {})
    if c1_report:
        contract = dict(c1_report.get("parametric_body_contract") or {})
        source_inventory_summary = dict(c1_report.get("source_inventory_summary") or {})
        family_rows = [
            {
                "family_id": str(item.get("family_id") or ""),
                "module_count": int(item.get("module_count") or 0),
                "classified_module_count": int(item.get("classified_module_count") or 0),
                "module_kind_counts": dict(item.get("module_kind_counts") or {}),
                "required_axes_present": dict(item.get("required_axes_present") or {}),
                "optional_axes_present": dict(item.get("optional_axes_present") or {}),
                "candidate_fixture_family": bool(item.get("candidate_fixture_family")),
            }
            for item in list(source_inventory_summary.get("per_family_results") or [])
        ]
        return {
            "status": str(c1_report.get("status") or c1_entry.get("status") or "unknown"),
            "gate_id": "parametric_body_contract_c1",
            "report_source_path": str(c1_entry.get("report_path") or ""),
            "source_root": str(source_inventory_summary.get("source_root") or ""),
            "family_count": int(dict(source_inventory_summary.get("counts") or {}).get("family_count") or len(family_rows)),
            "candidate_fixture_family_count": int(dict(source_inventory_summary.get("counts") or {}).get("candidate_fixture_family_count") or 0),
            "classified_module_count": int(dict(source_inventory_summary.get("counts") or {}).get("classified_module_count") or 0),
            "canonical_fixture_family_id": str(c1_report.get("body_family_id") or contract.get("body_family_id") or ""),
            "module_kind_counts": dict(source_inventory_summary.get("module_kind_counts") or {}),
            "families": family_rows,
            "contract_id": str(contract.get("contract_id") or ""),
            "core_module_id": str(contract.get("core_module_id") or ""),
            "supported_head_ids": list(contract.get("supported_head_ids") or []),
            "supported_bust_classes": list(contract.get("supported_bust_classes") or []),
            "supported_leg_length_profiles": list(contract.get("supported_leg_length_profiles") or []),
            "compatible_hair_ids": list(contract.get("compatible_hair_ids") or []),
        }
    report = c0_report
    entry = c0_entry
    if not report:
        return {
            "status": "missing",
            "gate_id": "modular_morphology_inventory_c0",
            "report_source_path": "",
            "source_root": "",
            "family_count": 0,
            "candidate_fixture_family_count": 0,
            "classified_module_count": 0,
            "canonical_fixture_family_id": "",
            "module_kind_counts": {},
            "families": [],
        }

    counts = dict(report.get("counts") or {})
    family_rows = [
        {
            "family_id": str(item.get("family_id") or ""),
            "module_count": int(item.get("module_count") or 0),
            "classified_module_count": int(item.get("classified_module_count") or 0),
            "module_kind_counts": dict(item.get("module_kind_counts") or {}),
            "required_axes_present": dict(item.get("required_axes_present") or {}),
            "optional_axes_present": dict(item.get("optional_axes_present") or {}),
            "candidate_fixture_family": bool(item.get("candidate_fixture_family")),
        }
        for item in list(report.get("per_family_results") or [])
    ]
    return {
        "status": str(report.get("status") or entry.get("status") or "unknown"),
        "gate_id": "modular_morphology_inventory_c0",
        "report_source_path": str(entry.get("report_path") or ""),
        "source_root": str(report.get("source_root") or ""),
        "family_count": int(counts.get("family_count") or len(family_rows)),
        "candidate_fixture_family_count": int(counts.get("candidate_fixture_family_count") or 0),
        "classified_module_count": int(counts.get("classified_module_count") or 0),
        "canonical_fixture_family_id": str(report.get("canonical_fixture_family_id") or ""),
        "module_kind_counts": dict(report.get("module_kind_counts") or {}),
        "families": family_rows,
    }


def build_parametric_body_contract(source_inventory_report: dict[str, Any]) -> dict[str, Any]:
    canonical_family_id = str(source_inventory_report.get("canonical_fixture_family_id") or "")
    family_rows = [dict(item) for item in list(source_inventory_report.get("per_family_results") or [])]
    selected_family = next(
        (family for family in family_rows if str(family.get("family_id") or "") == canonical_family_id),
        {},
    )
    module_ids_by_kind = {
        str(kind): sorted(str(module_id) for module_id in list(module_ids or []) if str(module_id))
        for kind, module_ids in dict(selected_family.get("module_ids_by_kind") or {}).items()
    }
    supported_head_ids = list(module_ids_by_kind.get("head") or [])
    supported_bust_classes = list(module_ids_by_kind.get("bust_variant") or [])
    supported_leg_length_profiles = list(module_ids_by_kind.get("leg_profile") or [])
    compatible_hair_ids = list(module_ids_by_kind.get("hair") or [])
    core_module_candidates = list(module_ids_by_kind.get("core_torso_arm") or [])
    core_module_id = core_module_candidates[0] if core_module_candidates else ""
    body_family_id = canonical_family_id
    contract_id = f"{body_family_id}::parametric_body_contract_c1" if body_family_id else ""

    return {
        "contract_id": contract_id,
        "contract_version": "c1",
        "body_family_id": body_family_id,
        "core_module_id": core_module_id,
        "supported_head_ids": supported_head_ids,
        "supported_bust_classes": supported_bust_classes,
        "supported_leg_length_profiles": supported_leg_length_profiles,
        "compatible_hair_ids": compatible_hair_ids,
        "fusion_recipe_id": f"fusion_recipe::{body_family_id}::canonical_v1" if body_family_id else "",
        "rig_profile_id": f"rig_profile::{body_family_id}::canonical_v1" if body_family_id else "",
        "material_profile_id": f"material_profile::{body_family_id}::canonical_v1" if body_family_id else "",
        "fixed_core": {
            "module_kind": "core_torso_arm",
            "runtime_module_swaps_supported": False,
        },
        "supported_axes": {
            "head": {
                "axis_id": "head",
                "selection_kind": "discrete",
                "required": True,
                "supported_values": supported_head_ids,
            },
            "bust": {
                "axis_id": "bust",
                "selection_kind": "discrete",
                "required": True,
                "supported_values": supported_bust_classes,
            },
            "leg_length": {
                "axis_id": "leg_length",
                "selection_kind": "discrete",
                "required": True,
                "supported_values": supported_leg_length_profiles,
            },
            "hair": {
                "axis_id": "hair",
                "selection_kind": "discrete_optional",
                "required": False,
                "supported_values": compatible_hair_ids,
            },
        },
        "combination_policy": {
            "domain_profile": "narrow_beauty_family_only",
            "runtime_raw_fragment_swaps_supported": False,
            "hair_in_core_contract": False,
            "notes": [
                "core torso and arms stay fixed in C1",
                "raw scan modules are not runtime-consumable in C1",
                "all contract values are derived from the selected canonical family only",
            ],
        },
        "selected_family_summary": {
            "family_id": body_family_id,
            "family_root": str(selected_family.get("family_root") or ""),
            "module_count": int(selected_family.get("module_count") or 0),
            "classified_module_count": int(selected_family.get("classified_module_count") or 0),
            "module_kind_counts": dict(selected_family.get("module_kind_counts") or {}),
            "module_ids_by_kind": module_ids_by_kind,
            "required_axes_present": dict(selected_family.get("required_axes_present") or {}),
            "optional_axes_present": dict(selected_family.get("optional_axes_present") or {}),
            "candidate_fixture_family": bool(selected_family.get("candidate_fixture_family")),
        },
    }
