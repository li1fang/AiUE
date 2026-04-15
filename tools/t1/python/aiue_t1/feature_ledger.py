from __future__ import annotations

from pathlib import Path
from typing import Any

from aiue_core.schema_utils import load_json


ALLOWED_LEDGER_STATUSES = {
    "稳定",
    "实验",
    "开发中",
    "规划",
    "暂停",
    "归档",
}

ALLOWED_LEDGER_PRIORITIES = {
    "P0",
    "P1",
    "P2",
    "P3",
    "未知",
}

ALLOWED_TRIAGE_STATES = {
    "待分诊",
    "已分诊",
    "进行中",
    "冻结",
    "不适用",
}

ALLOWED_IDEA_KINDS = {
    "平台能力",
    "质检实验",
    "展示能力",
    "治理工具",
    "外部集成",
}

ALLOWED_ENTRY_MODES = {
    "灵感",
    "问题驱动",
    "回归修补",
    "外部输入",
}


def load_feature_ledger(path: str | Path) -> dict[str, Any]:
    return dict(load_json(path) or {})


def validate_feature_ledger(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if str(payload.get("ledger_version") or "") != "v1":
        errors.append("ledger_version must be 'v1'")
    lines = list(payload.get("lines") or [])
    if not lines:
        errors.append("lines must not be empty")
        return errors
    seen_line_ids: set[str] = set()
    seen_item_ids: set[str] = set()
    for line in lines:
        line_id = str(line.get("line_id") or "")
        title_cn = str(line.get("title_cn") or "")
        if not line_id:
            errors.append("line_id must not be empty")
            continue
        if line_id in seen_line_ids:
            errors.append(f"duplicate line_id: {line_id}")
        seen_line_ids.add(line_id)
        if not title_cn:
            errors.append(f"line {line_id} is missing title_cn")
        items = list(line.get("items") or [])
        if not items:
            errors.append(f"line {line_id} must contain at least one item")
            continue
        for item in items:
            item_id = str(item.get("item_id") or "")
            if not item_id:
                errors.append(f"line {line_id} contains an empty item_id")
                continue
            if item_id in seen_item_ids:
                errors.append(f"duplicate item_id: {item_id}")
            seen_item_ids.add(item_id)
            if str(item.get("status") or "") not in ALLOWED_LEDGER_STATUSES:
                errors.append(f"item {item_id} has unsupported status: {item.get('status')}")
            priority = str(item.get("priority") or "")
            if priority and priority not in ALLOWED_LEDGER_PRIORITIES:
                errors.append(f"item {item_id} has unsupported priority: {priority}")
            triage_state = str(item.get("triage_state") or "")
            if triage_state and triage_state not in ALLOWED_TRIAGE_STATES:
                errors.append(f"item {item_id} has unsupported triage_state: {triage_state}")
            idea_kind = str(item.get("idea_kind") or "")
            if idea_kind and idea_kind not in ALLOWED_IDEA_KINDS:
                errors.append(f"item {item_id} has unsupported idea_kind: {idea_kind}")
            entry_mode = str(item.get("entry_mode") or "")
            if entry_mode and entry_mode not in ALLOWED_ENTRY_MODES:
                errors.append(f"item {item_id} has unsupported entry_mode: {entry_mode}")
            if not str(item.get("title_cn") or ""):
                errors.append(f"item {item_id} is missing title_cn")
    return errors


def summarize_feature_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    lines = list(payload.get("lines") or [])
    status_counts: dict[str, int] = {status: 0 for status in sorted(ALLOWED_LEDGER_STATUSES)}
    priority_counts: dict[str, int] = {priority: 0 for priority in sorted(ALLOWED_LEDGER_PRIORITIES)}
    triage_counts: dict[str, int] = {state: 0 for state in sorted(ALLOWED_TRIAGE_STATES)}
    idea_kind_counts: dict[str, int] = {kind: 0 for kind in sorted(ALLOWED_IDEA_KINDS)}
    entry_mode_counts: dict[str, int] = {mode: 0 for mode in sorted(ALLOWED_ENTRY_MODES)}
    line_counts: dict[str, int] = {}
    experimental_item_count = 0
    for line in lines:
        line_id = str(line.get("line_id") or "")
        items = list(line.get("items") or [])
        line_counts[line_id] = len(items)
        for item in items:
            status = str(item.get("status") or "")
            if status in status_counts:
                status_counts[status] += 1
            priority = str(item.get("priority") or "")
            if priority in priority_counts:
                priority_counts[priority] += 1
            triage_state = str(item.get("triage_state") or "")
            if triage_state in triage_counts:
                triage_counts[triage_state] += 1
            idea_kind = str(item.get("idea_kind") or "")
            if idea_kind in idea_kind_counts:
                idea_kind_counts[idea_kind] += 1
            entry_mode = str(item.get("entry_mode") or "")
            if entry_mode in entry_mode_counts:
                entry_mode_counts[entry_mode] += 1
            if any(
                str(item.get(field_name) or "")
                for field_name in ("idea_kind", "entry_mode", "promotion_rule_cn", "fixture_scope_cn")
            ):
                experimental_item_count += 1
    return {
        "ledger_version": str(payload.get("ledger_version") or ""),
        "line_count": len(lines),
        "item_count": sum(line_counts.values()),
        "experimental_item_count": experimental_item_count,
        "line_counts": line_counts,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "triage_counts": triage_counts,
        "idea_kind_counts": idea_kind_counts,
        "entry_mode_counts": entry_mode_counts,
    }


def _iter_ledger_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in list(payload.get("lines") or []):
        line_id = str(line.get("line_id") or "")
        line_title_cn = str(line.get("title_cn") or "")
        for item in list(line.get("items") or []):
            rows.append(
                {
                    "line_id": line_id,
                    "line_title_cn": line_title_cn,
                    "item_id": str(item.get("item_id") or ""),
                    "title_cn": str(item.get("title_cn") or ""),
                    "status": str(item.get("status") or ""),
                    "priority": str(item.get("priority") or ""),
                    "triage_state": str(item.get("triage_state") or ""),
                    "idea_kind": str(item.get("idea_kind") or ""),
                    "entry_mode": str(item.get("entry_mode") or ""),
                    "promotion_rule_cn": str(item.get("promotion_rule_cn") or ""),
                    "fixture_scope_cn": str(item.get("fixture_scope_cn") or ""),
                    "scheduling_hint_cn": str(item.get("scheduling_hint_cn") or ""),
                }
            )
    return rows


def build_feature_ledger_summary(repo_root: str | Path) -> dict[str, Any]:
    resolved_repo_root = Path(repo_root).expanduser().resolve()
    ledger_path = resolved_repo_root / "docs" / "governance" / "feature_ledger_cn.v1.json"
    if not ledger_path.exists():
        return {
            "status": "missing",
            "ledger_path": str(ledger_path),
            "summary": {},
            "validation_errors": [],
            "unknown_priority_items": [],
            "pending_triage_items": [],
        }
    try:
        payload = load_feature_ledger(ledger_path)
    except Exception as exc:
        return {
            "status": "error",
            "ledger_path": str(ledger_path),
            "summary": {},
            "validation_errors": [f"failed to load feature ledger: {exc}"],
            "unknown_priority_items": [],
            "pending_triage_items": [],
        }
    validation_errors = validate_feature_ledger(payload)
    rows = _iter_ledger_items(payload)
    unknown_priority_items = [dict(row) for row in rows if str(row.get("priority") or "") == "未知"]
    pending_triage_items = [dict(row) for row in rows if str(row.get("triage_state") or "") == "待分诊"]
    return {
        "status": "pass" if not validation_errors else "error",
        "ledger_path": str(ledger_path),
        "summary": summarize_feature_ledger(payload),
        "validation_errors": validation_errors,
        "unknown_priority_items": unknown_priority_items,
        "pending_triage_items": pending_triage_items,
    }
