from __future__ import annotations

import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_toy_yard_default_source_t2 import (  # noqa: E402
    build_communication_signal,
    select_bundle_candidate,
    select_solo_candidate,
)


def test_select_solo_candidate_prefers_consumer_ready_character_with_manifest():
    summary_payload = {
        "successes": [
            {
                "package_id": "pkg_weapon",
                "consumer_ready": True,
                "content_bucket": "Weapons",
            },
            {
                "package_id": "pkg_character_b",
                "consumer_ready": True,
                "content_bucket": "Characters",
            },
            {
                "package_id": "pkg_character_a",
                "consumer_ready": True,
                "content_bucket": "Characters",
            },
        ]
    }
    manifest_index = {
        "pkg_character_a": Path("C:/tmp/pkg_character_a/manifest.json"),
        "pkg_character_b": Path("C:/tmp/pkg_character_b/manifest.json"),
        "pkg_weapon": Path("C:/tmp/pkg_weapon/manifest.json"),
    }

    selected = select_solo_candidate(summary_payload, manifest_index)

    assert selected is not None
    assert selected["package_id"] == "pkg_character_a"
    assert Path(selected["manifest_path"]).name == "manifest.json"
    assert Path(selected["manifest_path"]).parent.name == "pkg_character_a"


def test_select_bundle_candidate_requires_both_manifests():
    registry_payload = {
        "ready_pairs": [
            {
                "sample_id": "sample_missing_weapon",
                "character_package_id": "pkg_character_only",
                "weapon_package_id": "pkg_weapon_missing",
            },
            {
                "sample_id": "sample_ok",
                "character_package_id": "pkg_character_ok",
                "weapon_package_id": "pkg_weapon_ok",
                "character_skeletal_mesh": "/Game/Characters/Char.Char",
                "weapon_skeletal_mesh": "/Game/Weapons/Weapon.Weapon",
            },
        ]
    }
    manifest_index = {
        "pkg_character_ok": Path("C:/tmp/pkg_character_ok/manifest.json"),
        "pkg_weapon_ok": Path("C:/tmp/pkg_weapon_ok/manifest.json"),
        "pkg_character_only": Path("C:/tmp/pkg_character_only/manifest.json"),
    }

    selected = select_bundle_candidate(registry_payload, manifest_index)

    assert selected is not None
    assert selected["sample_id"] == "sample_ok"
    assert Path(selected["character_manifest_path"]).parent.name == "pkg_character_ok"
    assert Path(selected["weapon_manifest_path"]).parent.name == "pkg_weapon_ok"


def test_build_communication_signal_prefers_toy_yard_for_packet_contract_issue():
    signal = build_communication_signal(
        manifest_check_payload={"status": "attention"},
        failed_requirements=[],
    )

    assert signal["should_contact_toy_yard"] is True
    assert signal["owner"] == "toy-yard"
    assert signal["reason"] == "export_packet_artifact_contract_issue"


def test_build_communication_signal_prefers_aiue_for_runtime_failure():
    signal = build_communication_signal(
        manifest_check_payload={"status": "pass"},
        failed_requirements=[
            {
                "id": "t2_bundle_refresh_failed",
                "message": "refresh failed",
            }
        ],
    )

    assert signal["should_contact_toy_yard"] is False
    assert signal["owner"] == "aiue"
    assert signal["reason"] == "aiue_runtime_or_consumption_issue"
