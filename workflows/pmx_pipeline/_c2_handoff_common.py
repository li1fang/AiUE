from __future__ import annotations

from typing import Any, Callable


ALLOWED_FIXTURE_SCOPES = {
    "canonical_fused_body",
    "full_body",
    "lower_body_core",
}

REMEDIATION_BY_ISSUE_ID = {
    "c2_manifest_missing": "Add canonical_fusion_fixture_manifest.json beside the exported mesh.",
    "c2_primary_mesh_missing": "Ensure primary_mesh_relative_path resolves to exactly one real mesh artifact.",
    "c2_fixture_id_missing": "Declare a stable fixture_id in the manifest.",
    "c2_body_family_missing": "Declare a stable body_family_id in the manifest.",
    "c2_fixture_scope_missing": "Declare fixture_scope in the manifest.",
    "c2_fixture_scope_invalid": "Change fixture_scope to one of the currently approved scopes.",
    "c2_source_module_ids_missing": "Populate source_module_ids so downstream tools can trace the fused artifact back to source modules.",
    "source_exporter_tool_missing": "Declare exporter.tool so downstream tools know which system produced the source handoff.",
    "source_exporter_version_missing": "Declare exporter.version so downstream tools can track the producing tool revision.",
    "source_linear_unit_missing": "Declare coordinate_system.linear_unit from the source package.",
    "source_up_axis_missing": "Declare coordinate_system.up_axis from the source package.",
    "source_forward_axis_missing": "Declare coordinate_system.forward_axis from the source package.",
    "c2_exporter_not_houdini": "For the strict C2 gate, set exporter.tool = houdini.",
    "c2_linear_unit_invalid": "For the strict C2 gate, export with UE-facing centimeter metadata and write linear_unit = cm.",
    "c2_up_axis_invalid": "For the strict C2 gate, export with explicit Z-up metadata and write up_axis = z.",
    "c2_fusion_recipe_missing": "Declare a stable fusion_recipe_id for deterministic replay.",
}


FailedRequirementFactory = Callable[..., dict[str, Any]]


def evaluate_provider_ready_source_handoff(
    fixture: dict[str, Any],
    *,
    make_failed_requirement: FailedRequirementFactory,
) -> tuple[str, list[dict[str, Any]]]:
    failed_requirements: list[dict[str, Any]] = []

    if not bool(fixture.get("manifest_present")):
        failed_requirements.append(
            make_failed_requirement(
                "c2_manifest_missing",
                "A provider-ready source handoff requires a canonical fusion manifest beside the Houdini mesh export.",
            )
        )

    if not str(fixture.get("primary_mesh_abs_path") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "c2_primary_mesh_missing",
                "A provider-ready source handoff requires exactly one resolvable primary mesh file.",
            )
        )

    fixture_scope = str(fixture.get("fixture_scope") or "")
    if not fixture_scope:
        failed_requirements.append(
            make_failed_requirement(
                "c2_fixture_scope_missing",
                "A provider-ready source handoff requires an explicit fixture_scope in the handoff manifest.",
            )
        )
    elif fixture_scope not in ALLOWED_FIXTURE_SCOPES:
        failed_requirements.append(
            make_failed_requirement(
                "c2_fixture_scope_invalid",
                "The current provider-ready handoff only accepts the approved narrow body scopes.",
                fixture_scope=fixture_scope,
                allowed_scopes=sorted(ALLOWED_FIXTURE_SCOPES),
            )
        )

    if not str(fixture.get("fixture_id") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "c2_fixture_id_missing",
                "A provider-ready source handoff requires a stable fixture_id.",
            )
        )

    if not str(fixture.get("body_family_id") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "c2_body_family_missing",
                "A provider-ready source handoff requires a body_family_id.",
            )
        )

    if not list(fixture.get("source_module_ids") or []):
        failed_requirements.append(
            make_failed_requirement(
                "c2_source_module_ids_missing",
                "A provider-ready source handoff requires source_module_ids so downstream tools can trace the fused asset back to modular inputs.",
            )
        )

    exporter = dict(fixture.get("exporter") or {})
    exporter_tool = str(exporter.get("tool") or "").lower()
    exporter_version = str(exporter.get("version") or "")
    if not exporter_tool:
        failed_requirements.append(
            make_failed_requirement(
                "source_exporter_tool_missing",
                "A provider-ready source handoff requires exporter.tool so downstream tools can understand source provenance.",
                exporter_tool=exporter_tool,
            )
        )
    if not exporter_version:
        failed_requirements.append(
            make_failed_requirement(
                "source_exporter_version_missing",
                "A provider-ready source handoff requires exporter.version so source provenance is replayable.",
            )
        )

    coordinate_system = dict(fixture.get("coordinate_system") or {})
    linear_unit = str(coordinate_system.get("linear_unit") or "").lower()
    up_axis = str(coordinate_system.get("up_axis") or "").lower()
    forward_axis = str(coordinate_system.get("forward_axis") or "").lower()
    if not linear_unit:
        failed_requirements.append(
            make_failed_requirement(
                "source_linear_unit_missing",
                "A provider-ready source handoff requires coordinate_system.linear_unit from the source package.",
                linear_unit=linear_unit,
            )
        )
    if not up_axis:
        failed_requirements.append(
            make_failed_requirement(
                "source_up_axis_missing",
                "A provider-ready source handoff requires coordinate_system.up_axis from the source package.",
                up_axis=up_axis,
            )
        )
    if not forward_axis:
        failed_requirements.append(
            make_failed_requirement(
                "source_forward_axis_missing",
                "A provider-ready source handoff requires coordinate_system.forward_axis from the source package.",
                forward_axis=forward_axis,
            )
        )

    if not str(fixture.get("fusion_recipe_id") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "c2_fusion_recipe_missing",
                "A provider-ready source handoff requires a fusion_recipe_id so the offline recipe can be replayed deterministically.",
            )
        )

    return ("pass" if not failed_requirements else "attention", failed_requirements)


def build_provider_ready_checklist(fixture: dict[str, Any], *, failed_ids: set[str]) -> list[dict[str, Any]]:
    coordinate_system = dict(fixture.get("coordinate_system") or {})
    exporter = dict(fixture.get("exporter") or {})
    source_module_ids = list(fixture.get("source_module_ids") or [])

    def _row(item_id: str, label: str, value: Any, *, passes: bool) -> dict[str, Any]:
        return {
            "item_id": item_id,
            "label": label,
            "value": value,
            "status": "pass" if passes else "attention",
        }

    return [
        _row(
            "manifest_present",
            "canonical_fusion_fixture_manifest.json exists",
            bool(fixture.get("manifest_present")),
            passes="c2_manifest_missing" not in failed_ids,
        ),
        _row(
            "primary_mesh",
            "primary mesh is resolvable",
            str(fixture.get("primary_mesh_relative_path") or ""),
            passes="c2_primary_mesh_missing" not in failed_ids,
        ),
        _row(
            "fixture_id",
            "fixture_id is declared",
            str(fixture.get("fixture_id") or ""),
            passes="c2_fixture_id_missing" not in failed_ids,
        ),
        _row(
            "body_family_id",
            "body_family_id is declared",
            str(fixture.get("body_family_id") or ""),
            passes="c2_body_family_missing" not in failed_ids,
        ),
        _row(
            "fixture_scope",
            "fixture_scope is approved",
            str(fixture.get("fixture_scope") or ""),
            passes="c2_fixture_scope_missing" not in failed_ids and "c2_fixture_scope_invalid" not in failed_ids,
        ),
        _row(
            "source_module_ids",
            "source_module_ids are declared",
            source_module_ids,
            passes="c2_source_module_ids_missing" not in failed_ids,
        ),
        _row(
            "exporter_tool",
            "exporter.tool is declared",
            str(exporter.get("tool") or ""),
            passes="source_exporter_tool_missing" not in failed_ids,
        ),
        _row(
            "exporter_version",
            "exporter.version is declared",
            str(exporter.get("version") or ""),
            passes="source_exporter_version_missing" not in failed_ids,
        ),
        _row(
            "linear_unit",
            "coordinate_system.linear_unit is declared",
            str(coordinate_system.get("linear_unit") or ""),
            passes="source_linear_unit_missing" not in failed_ids,
        ),
        _row(
            "up_axis",
            "coordinate_system.up_axis is declared",
            str(coordinate_system.get("up_axis") or ""),
            passes="source_up_axis_missing" not in failed_ids,
        ),
        _row(
            "forward_axis",
            "coordinate_system.forward_axis is declared",
            str(coordinate_system.get("forward_axis") or ""),
            passes="source_forward_axis_missing" not in failed_ids,
        ),
        _row(
            "fusion_recipe_id",
            "fusion_recipe_id is declared",
            str(fixture.get("fusion_recipe_id") or ""),
            passes="c2_fusion_recipe_missing" not in failed_ids,
        ),
    ]


def build_provider_ready_inventory(fixture: dict[str, Any]) -> dict[str, Any]:
    discovered_mesh_relative_paths = list(fixture.get("discovered_mesh_relative_paths") or [])
    discovered_texture_relative_paths = list(fixture.get("discovered_texture_relative_paths") or [])
    counts = dict(fixture.get("counts") or {})
    return {
        "manifest_present": bool(fixture.get("manifest_present")),
        "primary_mesh_relative_path": str(fixture.get("primary_mesh_relative_path") or ""),
        "primary_mesh_format": str(fixture.get("primary_mesh_format") or ""),
        "discovered_mesh_count": int(counts.get("discovered_mesh_count") or len(discovered_mesh_relative_paths)),
        "discovered_mesh_relative_paths": discovered_mesh_relative_paths,
        "discovered_texture_count": int(counts.get("discovered_texture_count") or len(discovered_texture_relative_paths)),
        "discovered_texture_relative_paths": discovered_texture_relative_paths,
        "declared_source_module_count": int(counts.get("source_module_count") or len(list(fixture.get("source_module_ids") or []))),
    }


def build_provider_ready_next_actions(failed_ids: set[str]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for issue_id in sorted(item for item in failed_ids if item):
        actions.append(
            {
                "issue_id": issue_id,
                "action": REMEDIATION_BY_ISSUE_ID.get(issue_id, "Review the failing requirement and update the handoff package accordingly."),
            }
        )
    return actions


def evaluate_strict_c2_requirements(
    fixture: dict[str, Any],
    *,
    make_failed_requirement: FailedRequirementFactory,
) -> list[dict[str, Any]]:
    failed_requirements: list[dict[str, Any]] = []
    exporter = dict(fixture.get("exporter") or {})
    exporter_tool = str(exporter.get("tool") or "").lower()
    if exporter_tool != "houdini":
        failed_requirements.append(
            make_failed_requirement(
                "c2_exporter_not_houdini",
                "The strict C2 gate requires exporter.tool = houdini.",
                exporter_tool=exporter_tool,
            )
        )

    coordinate_system = dict(fixture.get("coordinate_system") or {})
    linear_unit = str(coordinate_system.get("linear_unit") or "").lower()
    up_axis = str(coordinate_system.get("up_axis") or "").lower()
    if linear_unit not in {"cm", "centimeter", "centimeters"}:
        failed_requirements.append(
            make_failed_requirement(
                "c2_linear_unit_invalid",
                "The strict C2 gate requires UE-facing centimeter export metadata.",
                linear_unit=linear_unit,
            )
        )
    if up_axis != "z":
        failed_requirements.append(
            make_failed_requirement(
                "c2_up_axis_invalid",
                "The strict C2 gate requires explicit Z-up export metadata.",
                up_axis=up_axis,
            )
        )
    return failed_requirements
