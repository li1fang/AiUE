from __future__ import annotations

import html
import shutil
from datetime import datetime, timezone
from pathlib import Path

from aiue_core.schema_utils import write_json

from aiue_t1.report_index import build_report_index
from aiue_t1.slot_debugger import build_slot_debugger_payload

STYLE_CSS = """
body { font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
main { padding: 24px; max-width: 1400px; margin: 0 auto; }
h1, h2, h3 { color: #f8fafc; }
a { color: #93c5fd; }
.muted { color: #94a3b8; }
.grid { display: grid; gap: 16px; }
.cards { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.card { background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 16px; }
.status-pass { color: #86efac; }
.status-fail { color: #fca5a5; }
.status-unknown, .status-error { color: #fcd34d; }
.artifact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.artifact { background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 12px; }
.artifact img { width: 100%; border-radius: 8px; background: #020617; }
table { width: 100%; border-collapse: collapse; margin-top: 12px; }
th, td { border-bottom: 1px solid #334155; padding: 8px; text-align: left; vertical-align: top; }
code { background: #1e293b; padding: 2px 6px; border-radius: 6px; }
.section { margin-top: 28px; }
"""


def _run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _copy_file(source_path: str | Path, destination_path: Path) -> str:
    source = Path(source_path).expanduser().resolve()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination_path)
    return str(destination_path)


def _collect_preview_artifacts(report_index: dict) -> list[dict]:
    artifacts = []
    reports_by_gate_id = dict(report_index.get("reports_by_gate_id") or {})

    v1_report = dict((reports_by_gate_id.get("visual_proof_v1") or {}).get("report") or {})
    for shot in list((v1_report.get("visual_result") or {}).get("shots") or []):
        image_path = str(shot.get("image_path") or "")
        if image_path:
            artifacts.append({"title": f"V1 {shot.get('shot_id')}", "section": "Kernel Visual Proof", "source_path": image_path, "key": f"v1_{shot.get('shot_id')}"})

    q4_report = dict((reports_by_gate_id.get("multi_slot_quality_gate_q4") or {}).get("report") or {})
    for package in list(q4_report.get("per_package_results") or []):
        package_id = str(package.get("package_id") or "")
        for shot in list(package.get("strict_shot_results") or []):
            image_path = str(shot.get("image_path") or "")
            if image_path:
                artifacts.append({"title": f"Q4 {package_id} {shot.get('shot_id')}", "section": "Multi-Slot Quality", "source_path": image_path, "key": f"q4_{package_id}_{shot.get('shot_id')}"})

    r3_report = dict((reports_by_gate_id.get("live_fx_visual_quality_r3") or {}).get("report") or {})
    for package in list(r3_report.get("per_package_results") or []):
        package_id = str(package.get("package_id") or "")
        for shot in list(package.get("shot_results") or []):
            for phase_name in ("baseline_image_path", "with_fx_image_path"):
                image_path = str(shot.get(phase_name) or "")
                if image_path:
                    suffix = "baseline" if phase_name == "baseline_image_path" else "with_fx"
                    artifacts.append({"title": f"R3 {package_id} {shot.get('shot_id')} {suffix}", "section": "Live FX Visual Quality", "source_path": image_path, "key": f"r3_{package_id}_{shot.get('shot_id')}_{suffix}"})

    q5a_report = dict((reports_by_gate_id.get("visible_conflict_inspection_q5a") or {}).get("report") or {})
    for package in list(q5a_report.get("per_package_results") or []):
        package_id = str(package.get("package_id") or "")
        for shot in list(package.get("shot_results") or []):
            shot_id = str(shot.get("shot_id") or "")
            artifacts_payload = dict(shot.get("artifacts") or {})
            preview_specs = [
                ("body_only_image_path", "body_only"),
                ("slot_only_image_path", "slot_only"),
                ("combined_visible_image_path", "combined_visible"),
                ("debug_overlay_path", "debug_overlay"),
            ]
            for artifact_field, artifact_suffix in preview_specs:
                image_path = str(artifacts_payload.get(artifact_field) or "")
                if image_path:
                    artifacts.append(
                        {
                            "title": f"Q5A {package_id} {shot_id} {artifact_suffix}",
                            "section": "Visible Conflict Inspection",
                            "source_path": image_path,
                            "key": f"q5a_{package_id}_{shot_id}_{artifact_suffix}",
                        }
                    )
    e1_report = dict((reports_by_gate_id.get("showcase_demo_e1") or {}).get("report") or {})
    for package in list(e1_report.get("per_package_results") or []):
        package_id = str(package.get("package_id") or "")
        for shot in list(package.get("shot_results") or []):
            shot_id = str(shot.get("shot_id") or "")
            before_path = str(shot.get("before_image_path") or "")
            after_path = str(shot.get("after_image_path") or "")
            if before_path:
                artifacts.append(
                    {
                        "title": f"E1 {package_id} {shot_id} before",
                        "section": "Showcase Demo",
                        "source_path": before_path,
                        "key": f"e1_{package_id}_{shot_id}_before",
                    }
                )
            if after_path:
                artifacts.append(
                    {
                        "title": f"E1 {package_id} {shot_id} after",
                        "section": "Showcase Demo",
                        "source_path": after_path,
                        "key": f"e1_{package_id}_{shot_id}_after",
                    }
                )
    return artifacts


def _copy_reports(report_index: dict, reports_dir: Path) -> list[dict]:
    copied = []
    for category in ("active_line", "platform_line", "governance_line", "historical_other"):
        for entry in list((report_index.get("categories") or {}).get(category) or []):
            report_path = str(entry.get("report_path") or "")
            if not report_path:
                continue
            destination = reports_dir / Path(report_path).name
            _copy_file(report_path, destination)
            copied.append({"gate_id": entry.get("gate_id"), "category": category, "relative_path": str(destination.relative_to(reports_dir.parent)).replace("\\", "/")})
    return copied


def _copy_preview_images(preview_artifacts: list[dict], images_dir: Path) -> list[dict]:
    copied = []
    for artifact in preview_artifacts:
        source = Path(artifact["source_path"])
        if not source.exists():
            continue
        destination = images_dir / f"{artifact['key']}{source.suffix}"
        _copy_file(source, destination)
        copied.append({**artifact, "relative_path": str(destination.relative_to(images_dir.parent)).replace("\\", "/")})
    return copied


def _render_report_cards(entries: list[dict]) -> str:
    cards = []
    for entry in entries:
        status = str(entry.get("status") or "unknown")
        report_rel = f"reports/{Path(str(entry.get('report_path') or '')).name}"
        status_class = f"status-{status if status in {'pass', 'fail', 'unknown', 'error'} else 'unknown'}"
        cards.append(
            f"<article class=\"card\"><h3>{html.escape(str(entry.get('gate_id') or entry.get('name') or 'report'))}</h3><p class=\"{status_class}\"><strong>{html.escape(status.upper())}</strong></p><p class=\"muted\">{html.escape(str(entry.get('generated_at_utc') or 'unknown time'))}</p><p><a href=\"{html.escape(report_rel)}\">{html.escape(Path(report_rel).name)}</a></p></article>"
        )
    return "".join(cards)


def _render_preview_cards(preview_artifacts: list[dict]) -> str:
    return "".join(
        f"<article class=\"artifact\"><h3>{html.escape(item['title'])}</h3><p class=\"muted\">{html.escape(item['section'])}</p><img src=\"{html.escape(item['relative_path'])}\" alt=\"{html.escape(item['title'])}\" /></article>"
        for item in preview_artifacts
    )


def _render_r3_metrics(report_index: dict) -> str:
    r3_report = dict((dict(report_index.get("reports_by_gate_id") or {}).get("live_fx_visual_quality_r3") or {}).get("report") or {})
    rows = []
    for package in list(r3_report.get("per_package_results") or []):
        package_id = str(package.get("package_id") or "")
        for shot in list(package.get("shot_results") or []):
            crop_metrics = dict(shot.get("crop_metrics") or {})
            full_metrics = dict(shot.get("full_frame_metrics") or {})
            rows.append(
                f"<tr><td><code>{html.escape(package_id)}</code></td><td><code>{html.escape(str(shot.get('shot_id') or ''))}</code></td><td>{html.escape(str(shot.get('status') or ''))}</td><td>{float(crop_metrics.get('histogram_l1') or 0.0):.6f}</td><td>{float(crop_metrics.get('mean_abs_pixel_delta') or 0.0):.6f}</td><td>{float(full_metrics.get('histogram_l1') or 0.0):.6f}</td><td>{float(full_metrics.get('mean_abs_pixel_delta') or 0.0):.6f}</td></tr>"
            )
    if not rows:
        return "<p class=\"muted\">No R3 before/after metrics were available.</p>"
    return "<table><thead><tr><th>Package</th><th>Shot</th><th>Status</th><th>Crop Hist L1</th><th>Crop Mean Delta</th><th>Full Hist L1</th><th>Full Mean Delta</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_balance_card(report_index: dict) -> str:
    balance_report = dict((dict(report_index.get("reports_by_gate_id") or {}).get("dynamic_balance_governance_progress") or {}).get("report") or {})
    if not balance_report:
        return "<p class=\"muted\">No dynamic balance report was available.</p>"
    pressure_summary = dict(balance_report.get("pressure_summary") or {})
    recommendation = dict(balance_report.get("recommendation") or {})
    discussion_signal = dict(balance_report.get("discussion_signal") or {})
    return (
        "<article class=\"card\">"
        f"<h3>Dynamic Balance</h3>"
        f"<p><strong>Status:</strong> {html.escape(str(balance_report.get('status') or 'unknown'))}</p>"
        f"<p><strong>Recommended Next Round:</strong> {html.escape(str(recommendation.get('next_round_kind') or 'unknown'))}</p>"
        f"<p><strong>Stability Pressure:</strong> {html.escape(str((pressure_summary.get('stability_pressure') or {}).get('level') or 'unknown'))}</p>"
        f"<p><strong>Governance Pressure:</strong> {html.escape(str((pressure_summary.get('governance_pressure') or {}).get('level') or 'unknown'))}</p>"
        f"<p><strong>Progress Pressure:</strong> {html.escape(str((pressure_summary.get('progress_pressure') or {}).get('level') or 'unknown'))}</p>"
        f"<p class=\"muted\">Discussion reason: {html.escape(str(discussion_signal.get('reason') or 'none'))}</p>"
        "</article>"
    )


def _render_slot_debugger(slot_debugger: dict) -> str:
    blocks = []
    for package in list(slot_debugger.get("packages") or []):
        slot_rows = []
        for slot in list(package.get("slots") or []):
            tracked = ", ".join(f"{item.get('shot_id')}:{float(item.get('coverage_ratio') or 0.0):.4f}" for item in list(slot.get("tracked_coverages") or [])) or "-"
            attach_state = dict(slot.get("attach_state") or {})
            component = dict(slot.get("managed_component") or {})
            binding = dict(slot.get("binding") or {})
            slot_rows.append(
                f"<tr><td><code>{html.escape(str(slot.get('slot_name') or ''))}</code></td><td>{html.escape(str(binding.get('item_kind') or ''))}</td><td><code>{html.escape(str(component.get('component_name') or ''))}</code></td><td><code>{html.escape(str(attach_state.get('resolved_attach_socket_name') or attach_state.get('requested_attach_socket_name') or ''))}</code></td><td>{tracked}</td><td>{len(list(slot.get('slot_conflicts') or []))}</td><td>{len(list(slot.get('superseded_bindings') or []))}</td></tr>"
            )
        blocks.append(
            f"<article class=\"card\"><h3><code>{html.escape(str(package.get('package_id') or ''))}</code></h3><p class=\"muted\">{html.escape(str(package.get('host_blueprint_asset') or ''))}</p><table><thead><tr><th>Slot</th><th>Kind</th><th>Managed Component</th><th>Resolved Attach</th><th>Tracked Coverages</th><th>Conflicts</th><th>Superseded</th></tr></thead><tbody>{''.join(slot_rows)}</tbody></table></article>"
        )
    return "".join(blocks) if blocks else "<p class=\"muted\">No slot debugger data was available.</p>"


def _render_html(manifest: dict) -> str:
    report_index = dict(manifest.get("report_index") or {})
    categories = dict(report_index.get("categories") or {})
    preview_artifacts = list(manifest.get("artifacts", {}).get("preview_images") or [])
    slot_debugger = dict(manifest.get("slot_debugger") or {})
    counts = dict(report_index.get("counts") or {})
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>AiUE T1 Evidence Pack</title><link rel="stylesheet" href="assets/style.css" /></head>
<body><main>
<h1>AiUE T1 Evidence Pack</h1>
<p class="muted">Generated at {html.escape(str(manifest.get('generated_at_utc') or ''))}</p>
<section class="section"><h2>Summary</h2><div class="grid cards"><article class="card"><h3>Reports</h3><p>{int(counts.get('reports') or 0)}</p></article><article class="card"><h3>Active Line</h3><p>{int(counts.get('active_line_reports') or 0)}</p></article><article class="card"><h3>Platform Line</h3><p>{int(counts.get('platform_line_reports') or 0)}</p></article><article class="card"><h3>Governance Line</h3><p>{int(counts.get('governance_line_reports') or 0)}</p></article><article class="card"><h3>Passing Reports</h3><p>{int(counts.get('passing_reports') or 0)}</p></article></div></section>
<section class="section"><h2>Balance</h2>{_render_balance_card(report_index)}</section>
<section class="section"><h2>Active Line Reports</h2><div class="grid cards">{_render_report_cards(list(categories.get('active_line') or []))}</div></section>
<section class="section"><h2>Platform Line Reports</h2><div class="grid cards">{_render_report_cards(list(categories.get('platform_line') or []))}</div></section>
<section class="section"><h2>Governance Line Reports</h2><div class="grid cards">{_render_report_cards(list(categories.get('governance_line') or []))}</div></section>
<section class="section"><h2>Historical / Other Reports</h2><div class="grid cards">{_render_report_cards(list(categories.get('historical_other') or []))}</div></section>
<section class="section"><h2>Key Screenshot Previews</h2><div class="artifact-grid">{_render_preview_cards(preview_artifacts)}</div></section>
<section class="section"><h2>Before / After Metrics</h2>{_render_r3_metrics(report_index)}</section>
<section class="section"><h2>Slot Debugger</h2>{_render_slot_debugger(slot_debugger)}</section>
</main></body></html>"""


def build_evidence_pack(*, verification_root: Path, output_root: Path | None, latest_root: Path, repo_root: Path) -> dict:
    run_root = output_root or (repo_root / "Saved" / "tooling" / "t1" / _run_stamp())
    reports_dir = run_root / "reports"
    images_dir = run_root / "images"
    assets_dir = run_root / "assets"
    run_root.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    report_index = build_report_index(verification_root)
    slot_debugger = build_slot_debugger_payload(report_index)
    preview_artifacts = _collect_preview_artifacts(report_index)
    copied_reports = _copy_reports(report_index, reports_dir)
    copied_images = _copy_preview_images(preview_artifacts, images_dir)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tool_name": "AiUE",
        "tooling_phase": "T1",
        "verification_root": str(verification_root.resolve()),
        "external_candidate_sources": [],
        "report_index": {
            **report_index,
            "categories": {key: [{field: value for field, value in entry.items() if field != "report"} for entry in list(value or [])] for key, value in dict(report_index.get("categories") or {}).items()},
            "reports_by_gate_id": {key: {field: value for field, value in entry.items() if field != "report"} for key, entry in dict(report_index.get("reports_by_gate_id") or {}).items()},
        },
        "slot_debugger": slot_debugger,
        "artifacts": {
            "run_root": str(run_root.resolve()),
            "reports": copied_reports,
            "preview_images": copied_images,
            "planned_artifacts": {"mask": None, "depth": None},
        },
    }

    (assets_dir / "style.css").write_text(STYLE_CSS.strip() + "\n", encoding="utf-8")
    (run_root / "index.html").write_text(_render_html(manifest), encoding="utf-8")
    write_json(run_root / "manifest.json", manifest)

    if latest_root.exists():
        shutil.rmtree(latest_root)
    shutil.copytree(run_root, latest_root)
    return manifest
