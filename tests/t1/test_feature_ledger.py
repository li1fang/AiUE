from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
T1_ROOT = REPO_ROOT / "tools" / "t1" / "python"
CORE_ROOT = REPO_ROOT / "core" / "python"
for candidate in (T1_ROOT, CORE_ROOT):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from aiue_t1.feature_ledger import build_feature_ledger_summary, load_feature_ledger, summarize_feature_ledger, validate_feature_ledger  # noqa: E402


def test_feature_ledger_cn_v1_is_valid():
    ledger_path = REPO_ROOT / "docs" / "governance" / "feature_ledger_cn.v1.json"
    payload = load_feature_ledger(ledger_path)
    assert validate_feature_ledger(payload) == []


def test_feature_ledger_summary_has_expected_shape():
    ledger_path = REPO_ROOT / "docs" / "governance" / "feature_ledger_cn.v1.json"
    payload = load_feature_ledger(ledger_path)
    summary = summarize_feature_ledger(payload)
    assert summary["ledger_version"] == "v1"
    assert summary["line_count"] >= 6
    assert summary["item_count"] >= 20
    assert summary["status_counts"]["稳定"] >= 10
    assert summary["status_counts"]["开发中"] >= 1
    assert summary["status_counts"]["规划"] >= 1
    assert summary["priority_counts"]["未知"] >= 1
    assert summary["triage_counts"]["待分诊"] >= 1
    assert summary["experimental_item_count"] >= 1
    assert summary["idea_kind_counts"]["质检实验"] >= 1
    assert summary["entry_mode_counts"]["问题驱动"] >= 1


def test_feature_ledger_contains_unknown_priority_edge_band_task():
    ledger_path = REPO_ROOT / "docs" / "governance" / "feature_ledger_cn.v1.json"
    payload = load_feature_ledger(ledger_path)
    target = None
    for line in list(payload.get("lines") or []):
        for item in list(line.get("items") or []):
            if str(item.get("item_id") or "") == "q5a_edge_band_burial_detection":
                target = item
                break
        if target:
            break
    assert target is not None
    assert target["title_cn"] == "Q5A.x 红绿黄三色可见穿模检测"
    assert target["status"] == "规划"
    assert target["priority"] == "未知"
    assert target["triage_state"] == "待分诊"
    assert target["idea_kind"] == "质检实验"
    assert target["entry_mode"] == "问题驱动"
    assert "单夹具可重复评估" in str(target.get("promotion_rule_cn") or "")
    assert "body=红" in str(target.get("fixture_scope_cn") or "")
    assert "visible_conflict_inspection_q5a" in list(target.get("depends_on") or [])


def test_build_feature_ledger_summary_surfaces_experiment_metadata():
    summary = build_feature_ledger_summary(REPO_ROOT)
    assert summary["status"] == "pass"
    assert summary["summary"]["experimental_item_count"] >= 1
    assert summary["unknown_priority_items"]
    target = next(
        item for item in list(summary["unknown_priority_items"] or [])
        if str(item.get("item_id") or "") == "q5a_edge_band_burial_detection"
    )
    assert target["idea_kind"] == "质检实验"
    assert target["entry_mode"] == "问题驱动"
    assert "三色" in target["title_cn"]


def test_feature_ledger_tracks_real_clothing_input_gap():
    ledger_path = REPO_ROOT / "docs" / "governance" / "feature_ledger_cn.v1.json"
    payload = load_feature_ledger(ledger_path)
    target = None
    for line in list(payload.get("lines") or []):
        for item in list(line.get("items") or []):
            if str(item.get("item_id") or "") == "real_clothing_and_nude_fixture_supply":
                target = item
                break
        if target:
            break
    assert target is not None
    assert target["status"] == "规划"
    assert target["priority"] == "未知"
    assert target["triage_state"] == "待分诊"
    assert target["idea_kind"] == "外部集成"
    assert target["entry_mode"] == "问题驱动"
    assert "可分离的真实衣物素材" in str(target.get("promotion_rule_cn") or "")
    assert "裸体/近裸体 body baseline" in str(target.get("notes_cn") or "")
