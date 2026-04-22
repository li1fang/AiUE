from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any


SUPPORTED_BASE_MESH_EXTENSIONS = {".fbx", ".obj", ".c4d"}
MAJOR_VARIANT_PREFIX = "art_"


def sanitize_token(value: str) -> str:
    token = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", str(value).strip())
    token = re.sub(r"_+", "_", token).strip("_")
    return token or "sample"


def parse_base_mesh_inventory(inventory_path: str | Path) -> list[dict[str, str]]:
    path = Path(inventory_path).expanduser().resolve()
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    packages: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("### BM-"):
            if current:
                packages.append(current)
            current = {
                "archive_id": line.replace("### ", "").strip(),
                "source_archive": "",
                "family_guess": "",
                "trial_note": "",
            }
            continue
        if not current:
            continue
        source_match = re.match(r"- source archive:\s*`(.+?)`$", line)
        if source_match:
            current["source_archive"] = source_match.group(1)
            continue
        family_match = re.match(r"- family guess:\s*`(.+?)`$", line)
        if family_match:
            current["family_guess"] = family_match.group(1)
            continue
        trial_match = re.match(r"- trial note:\s*(.+)$", line)
        if trial_match:
            current["trial_note"] = trial_match.group(1).strip()
    if current:
        packages.append(current)
    return [package for package in packages if package.get("archive_id") and package.get("source_archive")]


def _zip_mesh_entries(archive_path: str | Path) -> list[str]:
    resolved_archive = Path(archive_path).expanduser().resolve()
    with zipfile.ZipFile(resolved_archive, "r") as archive:
        names = [
            name
            for name in archive.namelist()
            if Path(name).suffix.lower() in SUPPORTED_BASE_MESH_EXTENSIONS and not name.endswith("/")
        ]
    names.sort()
    return names


def _variant_from_entry(entry_name: str) -> str:
    path = Path(entry_name)
    stem = path.stem
    if stem:
        return stem
    return path.parent.name or path.name


def _stable_variant_token(entry_name: str, variant_id: str) -> str:
    variant_token = sanitize_token(variant_id)
    if variant_token != "sample":
        return variant_token
    digest = hashlib.sha1(str(entry_name).encode("utf-8", errors="ignore")).hexdigest()[:8]
    entry_token = sanitize_token(Path(entry_name).with_suffix("").as_posix().replace("/", "_"))
    if entry_token != "sample":
        return f"{entry_token}_{digest}"
    return f"mesh_{digest}"


def discover_base_mesh_items(archive_id: str, archive_path: str | Path) -> list[dict[str, Any]]:
    resolved_archive = Path(archive_path).expanduser().resolve()
    entries = _zip_mesh_entries(resolved_archive)
    if str(archive_id) == "BM-004":
        grouped: dict[str, dict[str, str]] = {}
        for entry in entries:
            parts = Path(entry).parts
            variant_name = next((part for part in parts if part.lower().startswith(MAJOR_VARIANT_PREFIX)), "")
            if not variant_name:
                continue
            slot = grouped.setdefault(variant_name, {})
            slot[Path(entry).suffix.lower().lstrip(".")] = entry
        items: list[dict[str, Any]] = []
        for variant_name, formats in sorted(grouped.items()):
            preferred_entry = formats.get("fbx") or formats.get("obj")
            if not preferred_entry:
                continue
            attempted_format = Path(preferred_entry).suffix.lower().lstrip(".")
            items.append(
                {
                    "archive_id": archive_id,
                    "archive_path": str(resolved_archive),
                    "variant_id": variant_name,
                    "mesh_entry": preferred_entry,
                    "attempted_format": attempted_format,
                    "format_fallback_used": attempted_format != "fbx",
                    "item_id": f"{archive_id.lower()}::{sanitize_token(variant_name)}::{attempted_format}",
                }
            )
        return items

    items = []
    for entry in entries:
        attempted_format = Path(entry).suffix.lower().lstrip(".")
        variant_id = _variant_from_entry(entry)
        variant_token = _stable_variant_token(entry, variant_id)
        items.append(
            {
                "archive_id": archive_id,
                "archive_path": str(resolved_archive),
                "variant_id": variant_id,
                "mesh_entry": entry,
                "attempted_format": attempted_format,
                "format_fallback_used": False,
                "item_id": f"{archive_id.lower()}::{variant_token}::{attempted_format}",
            }
        )
    return items


def extract_archive_entry(archive_path: str | Path, entry_name: str, output_root: str | Path) -> Path:
    resolved_archive = Path(archive_path).expanduser().resolve()
    resolved_output_root = Path(output_root).expanduser().resolve()
    resolved_output_root.mkdir(parents=True, exist_ok=True)
    destination = resolved_output_root / Path(entry_name).name
    with zipfile.ZipFile(resolved_archive, "r") as archive:
        with archive.open(entry_name, "r") as source_handle:
            with destination.open("wb") as destination_handle:
                shutil.copyfileobj(source_handle, destination_handle)
    return destination


def build_fixture_identity(archive_id: str, variant_id: str, item_id: str = "") -> dict[str, str]:
    archive_token = sanitize_token(archive_id.lower())
    variant_token = sanitize_token(variant_id)
    if variant_token == "sample" and item_id:
        parts = str(item_id).split("::")
        if len(parts) >= 3:
            variant_token = sanitize_token(parts[1])
    fixture_id = f"base_mesh_trial::{archive_token}::{variant_token}::v1"
    body_family_id = f"base_mesh_trial::{archive_token}"
    fusion_recipe_id = f"base_mesh_trial::{archive_token}::{variant_token}::source_wrap_v1"
    material_profile_id = f"material_profile::{archive_token}::{variant_token}::source_scan_v1"
    return {
        "fixture_id": fixture_id,
        "body_family_id": body_family_id,
        "fusion_recipe_id": fusion_recipe_id,
        "material_profile_id": material_profile_id,
    }


def ue_suitability_signal(
    *,
    attempted_format: str,
    status: str,
    bodypaint_handoff_candidate: bool,
    provider_ready_status: str,
    ue_smoke_status: str = "",
) -> str:
    normalized_format = str(attempted_format or "").lower()
    if normalized_format == "c4d":
        return "unsupported_format"
    if ue_smoke_status == "pass":
        return "strong_candidate"
    if ue_smoke_status == "fail":
        return "ue_smoke_attention"
    if bodypaint_handoff_candidate and provider_ready_status == "pass":
        return "strong_candidate"
    if status == "pass" and normalized_format == "obj":
        return "partial_candidate"
    if status == "blocked":
        return "blocked_candidate"
    if status == "fail":
        return "unlikely_candidate"
    return "unknown"


def summarize_format_behavior(per_item_results: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for item in per_item_results:
        attempted_format = str(item.get("attempted_format") or "unknown")
        bucket = summary.setdefault(
            attempted_format,
            {
                "item_count": 0,
                "pass_count": 0,
                "fail_count": 0,
                "blocked_count": 0,
                "bodypaint_candidate_count": 0,
                "ue_smoke_pass_count": 0,
            },
        )
        bucket["item_count"] += 1
        status = str(item.get("status") or "")
        if status in {"pass", "fail", "blocked"}:
            bucket[f"{status}_count"] += 1
        if item.get("bodypaint_handoff_candidate"):
            bucket["bodypaint_candidate_count"] += 1
        if str(item.get("ue_smoke_status") or "") == "pass":
            bucket["ue_smoke_pass_count"] += 1
    return summary


def render_feedback_markdown(
    *,
    runbook_path: str | Path,
    inventory_path: str | Path,
    bm0_report: dict[str, Any],
    bm1_report: dict[str, Any] | None = None,
    bm1_5_report: dict[str, Any] | None = None,
) -> str:
    bm0_counts = dict(bm0_report.get("counts") or {})
    bm1_counts = dict((bm1_report or {}).get("counts") or {})
    bm1_5_counts = dict((bm1_5_report or {}).get("counts") or {})
    format_summary = summarize_format_behavior(list(bm0_report.get("per_item_results") or []))

    friction_points: list[str] = []
    if "c4d" in format_summary:
        friction_points.append("- `C4D` currently has no direct AiUE consumer and still needs an external converter or adapter layer.")
    if any(str(item.get("attempted_format") or "") == "obj" for item in list(bm0_report.get("per_item_results") or [])):
        friction_points.append("- `OBJ` can enter the source-handoff trial, but it is not currently promoted to `ready_for_bodypaint`.")
    if any(str(item.get("archive_id") or "") == "BM-004" for item in list(bm0_report.get("per_item_results") or [])):
        friction_points.append("- The multi-variant pack still lacks an explicit runnable inventory, so AiUE has to infer the `Art_*` variants from directory conventions.")

    suggestions: list[str] = [
        "- Recommend that `toy-yard` mark a `preferred_primary_format = fbx` for future multi-format trio exports.",
        "- Recommend that `toy-yard` provide a machine-readable variant inventory for the multi-variant pack instead of only a raw archive.",
        "- Recommend that future base-mesh trial packets declare the runnable mesh list up front, so consumers do not have to rescan archive contents.",
    ]

    return "\n".join(
        [
            "# toy_yard_base_mesh_trial_feedback",
            "",
            f"- runbook: `{Path(runbook_path).expanduser().resolve()}`",
            f"- inventory: `{Path(inventory_path).expanduser().resolve()}`",
            "",
            "## Summary",
            "",
            f"- BM0 processed items: `{bm0_counts.get('item_count', 0)}`",
            f"- BM1 bodypaint-ready subset: `{bm1_counts.get('ready_candidate_count', 0)}`",
            f"- BM1.5 UE smoke passes: `{bm1_5_counts.get('passing_candidates', 0)}`",
            "",
            "## What Worked",
            "",
            "- The current `toy-yard` batch inventory is clear enough for AiUE to locate the four admitted archives directly.",
            "- The raw batch is already usable as a producer-side packet for a first real consumer trial.",
            "- The multi-variant anime pack looks valuable for future UE-facing and BodyPaint work and is worth keeping as a fixture family.",
            "",
            "## Friction Points",
            "",
            *(friction_points or ["- No new producer-side blocking issue showed up in this round."]),
            "",
            "## Suggestions",
            "",
            *suggestions,
            "",
        ]
    )


def render_ue_suitability_markdown(
    *,
    bm0_report: dict[str, Any],
    bm1_report: dict[str, Any] | None = None,
    bm1_5_report: dict[str, Any] | None = None,
) -> str:
    merged_items = [dict(item) for item in list(bm0_report.get("per_item_results") or [])]
    bm1_ready = {
        str(item.get("item_id") or ""): dict(item)
        for item in list((bm1_report or {}).get("per_candidate_results") or [])
        if str(item.get("item_id") or "")
    }
    bm1_5_results = {
        str(item.get("item_id") or ""): dict(item)
        for item in list((bm1_5_report or {}).get("per_candidate_results") or [])
        if str(item.get("item_id") or "")
    }

    lines = [
        "# base_mesh_ue_suitability_review",
        "",
        "## Batch Summary",
        "",
    ]
    for item in merged_items:
        bm1_5_item = bm1_5_results.get(str(item.get("item_id") or ""), {})
        if bm1_5_item:
            item["ue_smoke_status"] = str(bm1_5_item.get("status") or "")
    format_summary = summarize_format_behavior(merged_items)
    for attempted_format in sorted(format_summary):
        bucket = format_summary[attempted_format]
        lines.append(
            f"- `{attempted_format}`: items=`{bucket['item_count']}`, bodypaint_candidates=`{bucket['bodypaint_candidate_count']}`, ue_smoke_pass=`{bucket['ue_smoke_pass_count']}`"
        )
    lines.extend(["", "## Per Item Review", ""])

    for item in merged_items:
        item_id = str(item.get("item_id") or "")
        bm1_item = bm1_ready.get(item_id, {})
        bm1_5_item = bm1_5_results.get(item_id, {})
        displayed_signal = str(bm1_5_item.get("ue_suitability_signal") or item.get("ue_suitability_signal") or "")
        lines.extend(
            [
                f"### {item_id}",
                "",
                f"- archive: `{item.get('archive_id', '')}`",
                f"- variant: `{item.get('variant_id', '')}`",
                f"- mesh entry: `{item.get('mesh_entry', '')}`",
                f"- format: `{item.get('attempted_format', '')}`",
                f"- bm0 status: `{item.get('status', '')}`",
                f"- failure class: `{item.get('failure_class', '')}`",
                f"- bodypaint handoff candidate: `{bool(item.get('bodypaint_handoff_candidate'))}`",
                f"- bm1 status: `{bm1_item.get('status', '')}`",
                f"- bm1.5 ue smoke: `{bm1_5_item.get('status', '')}`",
                f"- ue suitability signal: `{displayed_signal}`",
                "",
            ]
        )

    return "\n".join(lines)


__all__ = [
    "SUPPORTED_BASE_MESH_EXTENSIONS",
    "build_fixture_identity",
    "discover_base_mesh_items",
    "extract_archive_entry",
    "parse_base_mesh_inventory",
    "render_feedback_markdown",
    "render_ue_suitability_markdown",
    "sanitize_token",
    "summarize_format_behavior",
    "ue_suitability_signal",
]
