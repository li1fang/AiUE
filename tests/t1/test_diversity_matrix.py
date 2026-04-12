from __future__ import annotations

from aiue_t1.diversity_matrix import build_diversity_axis, build_diversity_matrix_quality_summary, diversity_status_for_count
from aiue_t1.report_index import build_report_index
from tests.t2.helpers import build_fixture_pack


def test_diversity_status_for_count_uses_fixed_thresholds():
    assert diversity_status_for_count("character_variant_diversity", 2) == "covered"
    assert diversity_status_for_count("character_variant_diversity", 1) == "partial"
    assert diversity_status_for_count("character_variant_diversity", 0) == "missing"


def test_build_diversity_axis_normalizes_observed_values():
    axis = build_diversity_axis(
        "animation_variation",
        ["MM_Attack_01", "MM_Attack_01", "MM_Idle"],
        noun_phrase="verified animation presets",
    )
    assert axis["status"] == "covered"
    assert axis["distinct_count"] == 2
    assert axis["observed_values"] == ["MM_Attack_01", "MM_Idle"]


def test_build_diversity_matrix_quality_summary_reads_latest_report(tmp_path):
    pack = build_fixture_pack(tmp_path, include_dv1=True)
    report_index = build_report_index(pack["verification_root"])
    summary = build_diversity_matrix_quality_summary(report_index)
    assert summary["status"] == "pass"
    assert summary["covered_axis_count"] == 3
    assert summary["partial_axis_count"] == 3
    assert summary["distinct_counts"]["character_variant_diversity"] == 2
    assert summary["distinct_counts"]["animation_variation"] == 3
