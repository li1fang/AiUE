from __future__ import annotations

from pathlib import Path

from aiue_core.schema_utils import load_json

ACTIVE_LINE_GATE_IDS = [
    "visual_proof_v1",
    "demo_stage_d1_onboarding",
    "demo_cross_bundle_regression_d12",
    "showcase_demo_e1",
    "demo_shot_quality_gate_q1",
    "demo_composition_quality_gate_q2",
    "demo_semantic_framing_gate_q3",
    "multi_slot_quality_gate_q4",
]

PLATFORM_LINE_GATE_IDS = [
    "action_candidate_provider_a1",
    "source_contract_preflight_p0",
    "material_texture_proof_m1",
    "generic_slot_abstraction_p1",
    "clothing_vertical_slice_p2",
    "visible_conflict_inspection_q5a",
    "volumetric_fit_inspection_q5b",
    "volumetric_fit_spatial_evidence_q5bx",
    "volumetric_inspection_q5c_lite",
    "q5c_lite_contrast_lab",
    "fx_vertical_slice_p3",
    "multi_slot_composition_p4",
    "playable_core_smoke_pc1",
    "real_fx_item_kind_r2",
    "live_fx_visual_quality_r3",
]

BODY_PLATFORM_LINE_GATE_IDS = [
    "modular_morphology_inventory_c0",
    "parametric_body_contract_c1",
    "canonical_fusion_fixture_c2",
    "skeletal_transfer_proof_c3",
    "runtime_body_assembly_proof_c4",
    "inertial_base_layer_h0",
    "pose_traction_layer_h1",
    "collision_constraint_layer_h2",
    "runtime_surrogate_h3",
]

GOVERNANCE_LINE_GATE_IDS = [
    "dynamic_balance_governance_progress",
    "test_governance_round1",
    "qa_full_nightly",
    "qa_full_selected_lanes",
    "qa_lite_daily",
    "qa_lite_selected_lanes",
    "qa_body_platform",
    "qa_body_platform_selected_lanes",
    "diversity_matrix_dv2",
    "diversity_matrix_dv1",
    "manual_playable_demo_validation_pv1",
]


def _extract_external_candidate_sources(payload: dict, *, gate_id: str, report_path: Path) -> list[dict]:
    normalized = []
    for item in list(payload.get("external_candidate_sources") or []):
        source = dict(item or {})
        normalized.append(
            {
                "provider_name": str(source.get("provider_name") or ""),
                "source_id": str(source.get("source_id") or ""),
                "source_kind": str(source.get("source_kind") or ""),
                "candidate_count": int(source.get("candidate_count") or 0),
                "package_ids": [str(package_id) for package_id in list(source.get("package_ids") or []) if str(package_id)],
                "gate_id": gate_id,
                "report_path": str(report_path.resolve()),
            }
        )
    return normalized


def classify_gate(gate_id: str) -> tuple[str, int]:
    if gate_id in ACTIVE_LINE_GATE_IDS:
        return "active_line", ACTIVE_LINE_GATE_IDS.index(gate_id)
    if gate_id in PLATFORM_LINE_GATE_IDS:
        return "platform_line", PLATFORM_LINE_GATE_IDS.index(gate_id)
    if gate_id in BODY_PLATFORM_LINE_GATE_IDS:
        return "body_platform_line", BODY_PLATFORM_LINE_GATE_IDS.index(gate_id)
    if gate_id in GOVERNANCE_LINE_GATE_IDS:
        return "governance_line", GOVERNANCE_LINE_GATE_IDS.index(gate_id)
    return "historical_other", 999


def scan_latest_reports(verification_root: str | Path) -> list[dict]:
    root = Path(verification_root).expanduser().resolve()
    entries: list[dict] = []
    for report_path in sorted(root.glob("latest_*report.json")):
        try:
            payload = load_json(report_path)
        except Exception as exc:
            entries.append(
                {
                    "name": report_path.name,
                    "report_path": str(report_path.resolve()),
                    "status": "error",
                    "gate_id": "",
                    "category": "historical_other",
                    "category_order": 999,
                    "generated_at_utc": None,
                    "load_error": str(exc),
                    "report": None,
                    "external_candidate_sources": [],
                }
            )
            continue
        gate_id = str(payload.get("gate_id") or "")
        category, category_order = classify_gate(gate_id)
        external_candidate_sources = _extract_external_candidate_sources(
            payload,
            gate_id=gate_id,
            report_path=report_path,
        )
        entries.append(
            {
                "name": report_path.name,
                "report_path": str(report_path.resolve()),
                "gate_id": gate_id,
                "status": str(payload.get("status") or "unknown"),
                "generated_at_utc": payload.get("generated_at_utc"),
                "workflow_pack": payload.get("workflow_pack"),
                "schema_family": ((payload.get("compatibility") or {}).get("schema_family") if isinstance(payload.get("compatibility"), dict) else None),
                "category": category,
                "category_order": category_order,
                "report": payload,
                "external_candidate_sources": external_candidate_sources,
            }
        )
    entries.sort(key=lambda item: (item["category"], item["category_order"], item["gate_id"], item["name"]))
    return entries


def build_report_index(verification_root: str | Path) -> dict:
    reports = scan_latest_reports(verification_root)
    by_category = {
        "active_line": [item for item in reports if item["category"] == "active_line"],
        "platform_line": [item for item in reports if item["category"] == "platform_line"],
        "body_platform_line": [item for item in reports if item["category"] == "body_platform_line"],
        "governance_line": [item for item in reports if item["category"] == "governance_line"],
        "historical_other": [item for item in reports if item["category"] == "historical_other"],
    }
    return {
        "verification_root": str(Path(verification_root).expanduser().resolve()),
        "counts": {
            "reports": len(reports),
            "active_line_reports": len(by_category["active_line"]),
            "platform_line_reports": len(by_category["platform_line"]),
            "body_platform_line_reports": len(by_category["body_platform_line"]),
            "governance_line_reports": len(by_category["governance_line"]),
            "historical_other_reports": len(by_category["historical_other"]),
            "passing_reports": sum(1 for item in reports if item["status"] == "pass"),
        },
        "categories": by_category,
        "reports_by_gate_id": {item["gate_id"]: item for item in reports if item.get("gate_id")},
        "external_candidate_sources": [
            dict(source)
            for item in reports
            for source in list(item.get("external_candidate_sources") or [])
        ],
    }
