from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiue_core.schema_utils import load_json, write_json
from aiue_t2.demo_control_state import load_demo_control_state
from aiue_t2.demo_round_state import load_demo_round_state


REVIEW_STATE_FILENAME = "playable_demo_e2_review_state.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def review_state_path_from_session_manifest(session_manifest_path: str | Path | None) -> Path | None:
    if not session_manifest_path:
        return None
    resolved_session_path = Path(session_manifest_path).expanduser().resolve()
    return resolved_session_path.parent / REVIEW_STATE_FILENAME


def load_demo_review_state(session_manifest_path: str | Path | None) -> dict[str, Any]:
    resolved_path = review_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        return _missing_review_state_payload(None)
    if not resolved_path.exists():
        return _missing_review_state_payload(resolved_path)
    try:
        payload = load_json(resolved_path)
    except Exception as exc:
        return {
            **_missing_review_state_payload(resolved_path),
            "status": "error",
            "errors": [f"review_state_invalid_json:{exc}"],
        }
    return _normalize_review_state_payload(payload, resolved_path)


def build_demo_review_focus(demo_review_state: dict[str, Any], *, selected_package_id: str | None) -> dict[str, Any]:
    review_state_status = str(demo_review_state.get("status") or "missing")
    package_reviews = [dict(item) for item in list(demo_review_state.get("package_reviews") or [])]
    selected_review = next((item for item in package_reviews if str(item.get("package_id") or "") == str(selected_package_id or "")), None)
    if selected_review is None and package_reviews:
        selected_review = package_reviews[0]
    if selected_review is None or review_state_status == "missing":
        return {
            "status": "missing",
            "selected_package_id": str(selected_package_id or ""),
            "review_state_path": str(demo_review_state.get("review_state_path") or ""),
            "package_review_status": "",
            "action_review_status": "",
            "animation_review_status": "",
            "hero_before_image_path": "",
            "hero_after_image_path": "",
            "action_primary_before_image_path": "",
            "action_primary_after_image_path": "",
            "animation_primary_before_image_path": "",
            "animation_primary_after_image_path": "",
            "warning_flags": [],
            "failed_requirements": [],
        }
    action_review = dict(selected_review.get("action_review") or {})
    animation_review = dict(selected_review.get("animation_review") or {})
    return {
        "status": "pass" if review_state_status == "pass" and str(selected_review.get("status") or "") == "pass" else "attention",
        "selected_package_id": str(selected_review.get("package_id") or selected_package_id or ""),
        "review_state_path": str(demo_review_state.get("review_state_path") or ""),
        "package_review_status": str(selected_review.get("status") or ""),
        "action_review_status": str(action_review.get("status") or ""),
        "animation_review_status": str(animation_review.get("status") or ""),
        "hero_before_image_path": str(selected_review.get("hero_before_image_path") or ""),
        "hero_after_image_path": str(selected_review.get("hero_after_image_path") or ""),
        "action_primary_before_image_path": str(action_review.get("primary_before_image_path") or ""),
        "action_primary_after_image_path": str(action_review.get("primary_after_image_path") or ""),
        "animation_primary_before_image_path": str(animation_review.get("primary_before_image_path") or ""),
        "animation_primary_after_image_path": str(animation_review.get("primary_after_image_path") or ""),
        "warning_flags": [str(item) for item in list(selected_review.get("warning_flags") or [])],
        "failed_requirements": [str(item) for item in list(selected_review.get("failed_requirements") or [])],
    }


def build_demo_review_state(
    *,
    session_manifest_path: str | Path | None,
    demo_control_state: dict[str, Any] | None = None,
    demo_round_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_review_path = review_state_path_from_session_manifest(session_manifest_path)
    if not session_manifest_path:
        return _missing_review_state_payload(resolved_review_path)
    resolved_session_path = Path(session_manifest_path).expanduser().resolve()
    if not resolved_session_path.exists():
        return {
            **_missing_review_state_payload(resolved_review_path),
            "status": "error",
            "errors": [f"session_manifest_missing:{resolved_session_path}"],
        }
    try:
        session_payload = load_json(resolved_session_path)
    except Exception as exc:
        return {
            **_missing_review_state_payload(resolved_review_path),
            "status": "error",
            "errors": [f"session_manifest_invalid_json:{exc}"],
        }

    resolved_control_state = demo_control_state if demo_control_state is not None else load_demo_control_state(resolved_session_path)
    resolved_round_state = demo_round_state if demo_round_state is not None else load_demo_round_state(resolved_session_path)
    package_payloads = [dict(item) for item in list(session_payload.get("packages") or [])]
    package_reviews = [
        _build_package_review(
            package_payload,
            demo_control_state=resolved_control_state,
            demo_round_state=resolved_round_state,
        )
        for package_payload in package_payloads
    ]
    source_control_state_present = str(resolved_control_state.get("status") or "") not in {"", "missing"}
    source_round_state_present = str(resolved_round_state.get("status") or "") not in {"", "missing"}
    reviewable_sources_present = source_control_state_present or source_round_state_present

    summary = {
        "package_count": len(package_reviews),
        "reviewed_package_count": sum(
            1 for item in package_reviews if str(item.get("action_review", {}).get("status") or "") != "missing" or str(item.get("animation_review", {}).get("status") or "") != "missing"
        ),
        "passing_packages": sum(1 for item in package_reviews if str(item.get("status") or "") == "pass"),
        "action_review_passed": sum(1 for item in package_reviews if str(item.get("action_review", {}).get("status") or "") == "pass"),
        "animation_review_passed": sum(1 for item in package_reviews if str(item.get("animation_review", {}).get("status") or "") == "pass"),
        "packages_with_round_evidence": sum(1 for item in package_reviews if str(item.get("round_status") or "") == "pass"),
    }
    errors = [str(item) for item in list(resolved_control_state.get("errors") or [])] + [str(item) for item in list(resolved_round_state.get("errors") or [])]

    if not package_reviews:
        status = "missing"
    elif not reviewable_sources_present:
        status = "missing"
    elif all(str(item.get("status") or "") == "pass" for item in package_reviews):
        status = "pass"
    else:
        status = "attention"

    payload = {
        "status": status,
        "session_manifest_path": str(resolved_session_path),
        "session_id": str(session_payload.get("session_id") or ""),
        "generated_at_utc": now_utc(),
        "source_control_state_path": str(resolved_control_state.get("control_state_path") or ""),
        "source_round_state_path": str(resolved_round_state.get("round_state_path") or ""),
        "package_ids": [str(item.get("package_id") or "") for item in package_reviews],
        "summary": summary,
        "package_reviews": package_reviews,
        "errors": errors,
    }
    return _normalize_review_state_payload(payload, resolved_review_path)


def write_demo_review_state(
    *,
    session_manifest_path: str | Path | None,
    demo_control_state: dict[str, Any] | None = None,
    demo_round_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_path = review_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        raise RuntimeError("demo_review_state_session_manifest_missing")
    payload = build_demo_review_state(
        session_manifest_path=session_manifest_path,
        demo_control_state=demo_control_state,
        demo_round_state=demo_round_state,
    )
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(resolved_path, payload)
    return _normalize_review_state_payload(payload, resolved_path)


def _missing_review_state_payload(review_state_path: Path | None) -> dict[str, Any]:
    return {
        "status": "missing",
        "review_state_path": str(review_state_path) if review_state_path else "",
        "session_manifest_path": "",
        "session_id": "",
        "generated_at_utc": "",
        "source_control_state_path": "",
        "source_round_state_path": "",
        "package_ids": [],
        "summary": {
            "package_count": 0,
            "reviewed_package_count": 0,
            "passing_packages": 0,
            "action_review_passed": 0,
            "animation_review_passed": 0,
            "packages_with_round_evidence": 0,
        },
        "package_reviews": [],
        "errors": [],
    }


def _normalize_review_state_payload(payload: dict[str, Any], review_state_path: Path | None) -> dict[str, Any]:
    package_reviews = [dict(item) for item in list(payload.get("package_reviews") or [])]
    summary = dict(payload.get("summary") or {})
    return {
        "status": str(payload.get("status") or "missing"),
        "review_state_path": str(review_state_path) if review_state_path else "",
        "session_manifest_path": str(payload.get("session_manifest_path") or ""),
        "session_id": str(payload.get("session_id") or ""),
        "generated_at_utc": str(payload.get("generated_at_utc") or ""),
        "source_control_state_path": str(payload.get("source_control_state_path") or ""),
        "source_round_state_path": str(payload.get("source_round_state_path") or ""),
        "package_ids": [str(item) for item in list(payload.get("package_ids") or [])],
        "summary": {
            "package_count": int(summary.get("package_count") or len(package_reviews)),
            "reviewed_package_count": int(summary.get("reviewed_package_count") or 0),
            "passing_packages": int(summary.get("passing_packages") or 0),
            "action_review_passed": int(summary.get("action_review_passed") or 0),
            "animation_review_passed": int(summary.get("animation_review_passed") or 0),
            "packages_with_round_evidence": int(summary.get("packages_with_round_evidence") or 0),
        },
        "package_reviews": package_reviews,
        "errors": [str(item) for item in list(payload.get("errors") or [])],
    }


def _build_package_review(
    package_payload: dict[str, Any],
    *,
    demo_control_state: dict[str, Any],
    demo_round_state: dict[str, Any],
) -> dict[str, Any]:
    package_id = str(package_payload.get("package_id") or "")
    round_package = dict(_round_package_results_by_id(demo_round_state).get(package_id) or {})
    control_runs = dict((demo_control_state.get("last_runs_by_package") or {}).get(package_id) or {})

    action_run = _preferred_run_payload(
        round_run=dict(round_package.get("action_invoke") or {}),
        control_run=dict(control_runs.get("action_preview") or {}),
    )
    animation_run = _preferred_run_payload(
        round_run=dict(round_package.get("animation_invoke") or {}),
        control_run=dict(control_runs.get("animation_preview") or {}),
    )

    action_review = _build_run_review(action_run, request_kind="action_preview")
    animation_review = _build_run_review(animation_run, request_kind="animation_preview")

    hero_before_image_path = str(
        package_payload.get("hero_before_image_path")
        or dict(package_payload.get("evidence") or {}).get("hero_before_image_path")
        or ""
    )
    hero_after_image_path = str(
        package_payload.get("hero_after_image_path")
        or dict(package_payload.get("evidence") or {}).get("hero_after_image_path")
        or ""
    )
    failed_requirements: list[str] = []
    if str(round_package.get("status") or "") not in {"", "pass"}:
        failed_requirements.append("round_status_not_pass")
    if action_review["status"] != "pass":
        failed_requirements.extend([f"action:{item}" for item in list(action_review.get("failed_requirements") or [])])
    if animation_review["status"] != "pass":
        failed_requirements.extend([f"animation:{item}" for item in list(animation_review.get("failed_requirements") or [])])

    warning_flags = sorted(
        {
            *[str(item) for item in list(action_review.get("warning_flags") or [])],
            *[str(item) for item in list(animation_review.get("warning_flags") or [])],
        }
    )
    package_status = "pass" if not failed_requirements and action_review["status"] == "pass" and animation_review["status"] == "pass" else "fail"
    return {
        "package_id": package_id,
        "sample_id": str(package_payload.get("sample_id") or ""),
        "host_blueprint_asset": str(package_payload.get("host_blueprint_asset") or ""),
        "hero_shot_id": str(package_payload.get("hero_shot_id") or ""),
        "slot_names": [str(item) for item in list(package_payload.get("slot_names") or [])],
        "hero_before_image_path": hero_before_image_path,
        "hero_after_image_path": hero_after_image_path,
        "hero_before_image_present": _image_exists(hero_before_image_path),
        "hero_after_image_present": _image_exists(hero_after_image_path),
        "round_status": str(round_package.get("status") or ""),
        "status": package_status,
        "action_review": action_review,
        "animation_review": animation_review,
        "warning_flags": warning_flags,
        "failed_requirements": failed_requirements,
    }


def _preferred_run_payload(*, round_run: dict[str, Any], control_run: dict[str, Any]) -> dict[str, Any]:
    if round_run:
        return round_run
    if str(control_run.get("operation") or "") == "invoke":
        return control_run
    return {}


def _round_package_results_by_id(demo_round_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("package_id") or ""): dict(item)
        for item in list(demo_round_state.get("package_results") or [])
        if str(item.get("package_id") or "").strip()
    }


def _build_run_review(run_payload: dict[str, Any], *, request_kind: str) -> dict[str, Any]:
    if not run_payload:
        return {
            "status": "missing",
            "request_kind": request_kind,
            "selected_preset_id": "",
            "request_json_path": "",
            "result_json_path": "",
            "result_status": "",
            "host_key": "",
            "generated_at_utc": "",
            "primary_before_image_path": "",
            "primary_after_image_path": "",
            "before_image_present": False,
            "after_image_present": False,
            "subject_visible": False,
            "verified": False,
            "warning_flags": [],
            "failed_requirements": ["run_missing"],
        }

    credibility_summary = dict(run_payload.get("credibility_summary") or {})
    key_image_paths = dict(run_payload.get("key_image_paths") or {})
    primary_before_image_path = str(key_image_paths.get("primary_before") or "")
    primary_after_image_path = str(key_image_paths.get("primary_after") or "")
    verification_key = "action_motion_verified" if request_kind == "action_preview" else "animation_pose_verified"
    selected_preset_id = (
        str(run_payload.get("selected_action_preset_id") or "")
        if request_kind == "action_preview"
        else str(run_payload.get("selected_animation_preset_id") or "")
    )
    failed_requirements: list[str] = []
    if str(run_payload.get("result_status") or "") != "pass":
        failed_requirements.append("result_status_not_pass")
    if not primary_before_image_path or not _image_exists(primary_before_image_path):
        failed_requirements.append("before_image_missing")
    if not primary_after_image_path or not _image_exists(primary_after_image_path):
        failed_requirements.append("after_image_missing")
    if not bool(credibility_summary.get("subject_visible")):
        failed_requirements.append("subject_not_visible")
    if not bool(credibility_summary.get(verification_key)):
        failed_requirements.append(f"{verification_key}_false")

    return {
        "status": "pass" if not failed_requirements else "fail",
        "request_kind": request_kind,
        "selected_preset_id": selected_preset_id,
        "request_json_path": str(run_payload.get("request_json_path") or ""),
        "result_json_path": str(run_payload.get("result_json_path") or ""),
        "result_status": str(run_payload.get("result_status") or ""),
        "host_key": str(run_payload.get("host_key") or ""),
        "generated_at_utc": str(run_payload.get("generated_at_utc") or ""),
        "primary_before_image_path": primary_before_image_path,
        "primary_after_image_path": primary_after_image_path,
        "before_image_present": _image_exists(primary_before_image_path),
        "after_image_present": _image_exists(primary_after_image_path),
        "subject_visible": bool(credibility_summary.get("subject_visible")),
        "verified": bool(credibility_summary.get(verification_key)),
        "warning_flags": [str(item) for item in list(credibility_summary.get("warning_flags") or [])],
        "failed_requirements": failed_requirements,
    }


def _image_exists(image_path: str | None) -> bool:
    if not image_path:
        return False
    return Path(image_path).expanduser().exists()
