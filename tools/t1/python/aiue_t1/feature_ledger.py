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
            if not str(item.get("title_cn") or ""):
                errors.append(f"item {item_id} is missing title_cn")
    return errors


def summarize_feature_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    lines = list(payload.get("lines") or [])
    status_counts: dict[str, int] = {status: 0 for status in sorted(ALLOWED_LEDGER_STATUSES)}
    priority_counts: dict[str, int] = {priority: 0 for priority in sorted(ALLOWED_LEDGER_PRIORITIES)}
    triage_counts: dict[str, int] = {state: 0 for state in sorted(ALLOWED_TRIAGE_STATES)}
    line_counts: dict[str, int] = {}
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
    return {
        "ledger_version": str(payload.get("ledger_version") or ""),
        "line_count": len(lines),
        "item_count": sum(line_counts.values()),
        "line_counts": line_counts,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "triage_counts": triage_counts,
    }
