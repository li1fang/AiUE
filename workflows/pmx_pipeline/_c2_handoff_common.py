from __future__ import annotations

from typing import Any, Callable


ALLOWED_FIXTURE_SCOPES = {
    "canonical_fused_body",
    "full_body",
    "lower_body_core",
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
    if exporter_tool != "houdini":
        failed_requirements.append(
            make_failed_requirement(
                "c2_exporter_not_houdini",
                "The current provider-ready source handoff requires exporter.tool = houdini.",
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
                "A provider-ready source handoff requires UE-facing centimeter export metadata.",
                linear_unit=linear_unit,
            )
        )
    if up_axis != "z":
        failed_requirements.append(
            make_failed_requirement(
                "c2_up_axis_invalid",
                "A provider-ready source handoff requires explicit Z-up export metadata.",
                up_axis=up_axis,
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
            "exporter.tool = houdini",
            str(exporter.get("tool") or ""),
            passes="c2_exporter_not_houdini" not in failed_ids,
        ),
        _row(
            "linear_unit",
            "coordinate_system.linear_unit = cm",
            str(coordinate_system.get("linear_unit") or ""),
            passes="c2_linear_unit_invalid" not in failed_ids,
        ),
        _row(
            "up_axis",
            "coordinate_system.up_axis = z",
            str(coordinate_system.get("up_axis") or ""),
            passes="c2_up_axis_invalid" not in failed_ids,
        ),
        _row(
            "fusion_recipe_id",
            "fusion_recipe_id is declared",
            str(fixture.get("fusion_recipe_id") or ""),
            passes="c2_fusion_recipe_missing" not in failed_ids,
        ),
    ]
