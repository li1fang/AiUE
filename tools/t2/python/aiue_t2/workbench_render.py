from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QTreeWidgetItem

from aiue_t2.demo_review_compare_state import build_demo_review_compare_focus
from aiue_t2.demo_review_history_state import build_demo_review_history_focus
from aiue_t2.demo_review_state import build_demo_review_focus, build_demo_review_state, write_demo_review_state
from aiue_t2.state import CATEGORY_LABELS, CATEGORY_ORDER, DemoPackageRecord, PreviewImageRecord, ReportRecord, build_q5c_contrast_focus


class WorkbenchRenderMixin:
    def advance_debug_cycle(self, step: int) -> None:
        gate_ids = list(self.report_items_by_gate_id)
        if gate_ids:
            self._select_report(gate_ids[step % len(gate_ids)])
        if self.preview_list.count():
            self.preview_list.setCurrentRow(step % self.preview_list.count())
        if self.demo_session_package_list.count():
            self.demo_session_package_list.setCurrentRow(step % self.demo_session_package_list.count())
        if self.demo_action_preset_list.count():
            self.demo_action_preset_list.setCurrentRow(step % self.demo_action_preset_list.count())
        if self.demo_animation_preset_list.count():
            self.demo_animation_preset_list.setCurrentRow(step % self.demo_animation_preset_list.count())
        if self.tabs.count():
            self.tabs.setCurrentIndex(step % self.tabs.count())

    def open_selected_report(self) -> None:
        report = self._selected_report_record()
        if not report:
            return
        target = report.report_artifact_path or report.report_source_path
        self._open_in_explorer(target)

    def open_selected_image(self) -> None:
        preview = self._selected_preview_record()
        if not preview:
            return
        self._open_in_explorer(preview.image_path)

    def open_pack_root(self) -> None:
        self._open_in_explorer(self.app_state.pack_root)

    def _render_state(self) -> None:
        self._render_errors()
        counts = dict(self.app_state.summary_counts)
        self.summary_cards["reports"].set_value(int(counts.get("reports") or 0))
        self.summary_cards["active"].set_value(int(counts.get("active_line_reports") or 0))
        self.summary_cards["platform"].set_value(int(counts.get("platform_line_reports") or 0))
        self.summary_cards["body"].set_value(int(counts.get("body_platform_line_reports") or 0))
        self.summary_cards["governance"].set_value(int(counts.get("governance_line_reports") or 0))
        self.summary_cards["passing"].set_value(int(counts.get("passing_reports") or 0))
        self._render_test_governance_summary()
        self._render_pv1_signoff_summary()
        self._render_quality_summaries()
        self._render_report_tree()
        self._render_details()
        self._render_preview_images()
        self._render_metrics()
        self._render_slot_table()
        self._render_demo_session()
        self._render_demo_request()
        self._render_demo_review()

    def _render_errors(self) -> None:
        if not self.app_state.errors:
            self.error_banner.setVisible(False)
            self.error_banner.setText("")
            return
        lines = [f"[{error.code}] {error.message}" for error in self.app_state.errors]
        self.error_banner.setText("\n".join(lines))
        self.error_banner.setVisible(True)

    def _render_test_governance_summary(self) -> None:
        summary = self.app_state.test_governance
        if summary.status == "missing":
            self.test_governance_summary.setVisible(False)
            self.test_governance_summary.setText("")
            return
        required_text = ", ".join(summary.required_lane_ids) if summary.required_lane_ids else "none"
        automation_blind_spot_text = (
            ", ".join(summary.high_priority_automation_blind_spot_ids)
            if summary.high_priority_automation_blind_spot_ids
            else "none"
        )
        signoff_blind_spot_text = (
            ", ".join(summary.high_priority_signoff_blind_spot_ids)
            if summary.high_priority_signoff_blind_spot_ids
            else "none"
        )
        failed_text = ", ".join(summary.failed_lane_ids) if summary.failed_lane_ids else "none"
        self.test_governance_summary.setText(
            "Test Governance "
            f"{summary.status.upper()} | checkpoint_ready {summary.checkpoint_ready} | "
            f"automation_ready {summary.automation_checkpoint_ready} | "
            f"signoff_ready {summary.signoff_checkpoint_ready} | "
            f"required {required_text} | failed {failed_text} | "
            f"automation blind spots {automation_blind_spot_text} | "
            f"signoff blind spots {signoff_blind_spot_text}"
        )
        self.test_governance_summary.setVisible(True)

    def _render_pv1_signoff_summary(self) -> None:
        summary = self.app_state.pv1_signoff
        if summary.status == "missing":
            self.pv1_signoff_summary.setVisible(False)
            self.pv1_signoff_summary.setText("")
            return
        checked_packages_text = ", ".join(summary.checked_package_ids) if summary.checked_package_ids else "none"
        notes_text = summary.notes or "none"
        operator_text = summary.operator or "unknown"
        requested_text = summary.requested_signoff_status or "n/a"
        self.pv1_signoff_summary.setText(
            "PV1 Signoff "
            f"{summary.status.upper()} | requested {requested_text} | "
            f"operator {operator_text} | checked_packages {summary.checked_package_count} | "
            f"package_ids {checked_packages_text} | notes {notes_text}"
        )
        self.pv1_signoff_summary.setVisible(True)

    def _render_quality_summaries(self) -> None:
        diversity_summary = dict((self.app_state.quality_summaries or {}).get("diversity_matrix") or {})
        e2c_summary = dict((self.app_state.quality_summaries or {}).get("e2c_showcase_polish") or {})
        a1_summary = dict((self.app_state.quality_summaries or {}).get("a1_candidate_provider") or {})
        selected_package_id = str(self.view_state.selected_package_id or "")
        if not diversity_summary or str(diversity_summary.get("status") or "missing") == "missing":
            self.diversity_matrix_summary.setVisible(False)
            self.diversity_matrix_summary.setText("")
        else:
            distinct_counts = dict(diversity_summary.get("distinct_counts") or {})
            gate_id = str(diversity_summary.get("gate_id") or "diversity_matrix")
            gate_label = "DV2" if gate_id == "diversity_matrix_dv2" else "DV1" if gate_id == "diversity_matrix_dv1" else gate_id
            self.diversity_matrix_summary.setText(
                f"{gate_label} Diversity Matrix "
                f"{str(diversity_summary.get('status') or 'unknown').upper()} | "
                f"covered {int(diversity_summary.get('covered_axis_count') or 0)} | "
                f"partial {int(diversity_summary.get('partial_axis_count') or 0)} | "
                f"characters {int(distinct_counts.get('character_variant_diversity') or 0)} | "
                f"weapons {int(distinct_counts.get('weapon_variant_diversity') or 0)} | "
                f"clothing {int(distinct_counts.get('clothing_fixture_diversity') or 0)} | "
                f"fx {int(distinct_counts.get('fx_fixture_diversity') or 0)} | "
                f"actions {int(distinct_counts.get('action_variation') or 0)} | "
                f"animations {int(distinct_counts.get('animation_variation') or 0)}"
            )
            self.diversity_matrix_summary.setVisible(True)

        selected_e2c_package = next(
            (
                dict(item)
                for item in list(e2c_summary.get("packages") or [])
                if str(item.get("package_id") or "") == selected_package_id
            ),
            {},
        )
        if not e2c_summary or str(e2c_summary.get("status") or "missing") == "missing":
            self.demo_showcase_summary.setVisible(False)
            self.demo_showcase_summary.setText("")
        else:
            if not selected_e2c_package and list(e2c_summary.get("packages") or []):
                selected_e2c_package = dict(list(e2c_summary.get("packages") or [])[0] or {})
            counts = dict(e2c_summary.get("counts") or {})
            package_label = str(selected_e2c_package.get("package_id") or selected_package_id or "n/a")
            polish_summary = dict(selected_e2c_package.get("polish_summary") or {})
            self.demo_showcase_summary.setText(
                "E2C Showcase Polish "
                f"{str(e2c_summary.get('status') or 'unknown').upper()} | "
                f"passing {int(counts.get('passing_packages') or 0)}/{int(counts.get('resolved_package_count') or 0)} | "
                f"package {package_label} | "
                f"hero {'yes' if bool(polish_summary.get('hero_ready')) else 'no'} | "
                f"material {'yes' if bool(polish_summary.get('material_ready')) else 'no'} | "
                f"replay {'yes' if bool(polish_summary.get('replay_ready')) else 'no'} | "
                f"compare {'yes' if bool(polish_summary.get('compare_ready')) else 'no'} | "
                f"history {'yes' if bool(polish_summary.get('history_ready')) else 'no'} | "
                f"diversity {'yes' if bool(polish_summary.get('diversity_ready')) else 'no'}"
            )
            self.demo_showcase_summary.setVisible(True)

        selected_a1_package = next(
            (
                dict(item)
                for item in list(a1_summary.get("packages") or [])
                if str(item.get("package_id") or "") == selected_package_id
            ),
            {},
        )
        if not a1_summary or str(a1_summary.get("status") or "missing") == "missing":
            self.a1_candidate_provider_summary.setVisible(False)
            self.a1_candidate_provider_summary.setText("")
        else:
            if not selected_a1_package and list(a1_summary.get("packages") or []):
                selected_a1_package = dict(list(a1_summary.get("packages") or [])[0] or {})
            counts = dict(a1_summary.get("counts") or {})
            provider_names = ", ".join(
                str(item.get("provider_name") or "provider")
                for item in list(a1_summary.get("candidate_sources") or [])
                if str(item.get("provider_name") or "")
            ) or "none"
            candidate_label = str(selected_a1_package.get("candidate_id") or "n/a")
            credibility = dict(selected_a1_package.get("credibility_summary") or {})
            self.a1_candidate_provider_summary.setText(
                "A1 Candidate Provider "
                f"{str(a1_summary.get('status') or 'unknown').upper()} | "
                f"passing {int(counts.get('passing_candidates') or 0)}/{int(counts.get('resolved_candidate_count') or 0)} | "
                f"providers {provider_names} | "
                f"package {str(selected_a1_package.get('package_id') or selected_package_id or 'n/a')} | "
                f"candidate {candidate_label} | "
                f"pose {'yes' if bool(credibility.get('animation_pose_verified')) else 'no'} | "
                f"motion {'yes' if bool(credibility.get('external_motion_verified')) else 'no'}"
            )
            self.a1_candidate_provider_summary.setVisible(True)

        m1_summary = dict((self.app_state.quality_summaries or {}).get("m1_material_proof") or {})
        body_platform_summary = dict((self.app_state.quality_summaries or {}).get("body_platform") or {})
        selected_m1_package = next(
            (
                dict(item)
                for item in list(m1_summary.get("packages") or [])
                if str(item.get("package_id") or "") == selected_package_id
            ),
            {},
        )
        if not m1_summary or str(m1_summary.get("status") or "missing") == "missing":
            self.material_proof_summary.setVisible(False)
            self.material_proof_summary.setText("")
        else:
            if not selected_m1_package and list(m1_summary.get("packages") or []):
                selected_m1_package = dict(list(m1_summary.get("packages") or [])[0] or {})
            package_label = str(selected_m1_package.get("package_id") or selected_package_id or "n/a")
            self.material_proof_summary.setText(
                "M1 Material Proof "
                f"{str(m1_summary.get('status') or 'unknown').upper()} | "
                f"package {package_label} | "
                f"character textures {int(selected_m1_package.get('character_imported_texture_count') or 0)}/{int(selected_m1_package.get('character_expected_texture_count') or 0)} | "
                f"weapon textures {int(selected_m1_package.get('weapon_imported_texture_count') or 0)}/{int(selected_m1_package.get('weapon_expected_texture_count') or 0)} | "
                f"main slots {int(selected_m1_package.get('main_mesh_material_slot_count') or 0)} | "
                f"weapon slots {int(selected_m1_package.get('weapon_material_slot_count') or 0)}"
            )
            self.material_proof_summary.setVisible(True)
        if not body_platform_summary or str(body_platform_summary.get("status") or "missing") == "missing":
            self.body_platform_summary.setVisible(False)
            self.body_platform_summary.setText("")
        else:
            module_kind_counts = dict(body_platform_summary.get("module_kind_counts") or {})
            contract_id = str(body_platform_summary.get("contract_id") or "")
            core_module_id = str(body_platform_summary.get("core_module_id") or "")
            summary_parts = [
                "Body Platform",
                str(body_platform_summary.get("status") or "unknown").upper(),
            ]
            gate_id = str(body_platform_summary.get("gate_id") or "")
            if gate_id:
                summary_parts.append(gate_id)
            summary_parts.extend(
                [
                    f"families {int(body_platform_summary.get('family_count') or 0)}",
                    f"candidates {int(body_platform_summary.get('candidate_fixture_family_count') or 0)}",
                    f"canonical {str(body_platform_summary.get('canonical_fixture_family_id') or 'n/a')}",
                ]
            )
            if contract_id:
                summary_parts.append(f"contract {contract_id}")
            if core_module_id:
                summary_parts.append(f"core {core_module_id}")
            summary_parts.extend(
                [
                    f"head {int(module_kind_counts.get('head') or 0)}",
                    f"bust {int(module_kind_counts.get('bust_variant') or 0)}",
                    f"leg {int(module_kind_counts.get('leg_profile') or 0)}",
                    f"core {int(module_kind_counts.get('core_torso_arm') or 0)}",
                    f"hair {int(module_kind_counts.get('hair') or 0)}",
                ]
            )
            self.body_platform_summary.setText(
                " | ".join(summary_parts)
            )
            self.body_platform_summary.setVisible(True)
        q5c_summary = dict((self.app_state.quality_summaries or {}).get("q5c_lite") or {})
        if not q5c_summary or str(q5c_summary.get("status") or "missing") == "missing":
            self.q5c_quality_summary.setVisible(False)
            self.q5c_quality_summary.setText("")
        else:
            diagnostic_counts = dict(q5c_summary.get("diagnostic_class_counts") or {})
            classes_text = ", ".join(
                f"{key}:{int(value)}"
                for key, value in sorted(diagnostic_counts.items())
            ) or "none"
            focus_package_id = str(q5c_summary.get("focus_package_id") or "")
            focus_metric = str(q5c_summary.get("focus_metric") or "")
            focus_margin = float(q5c_summary.get("focus_margin_to_failure") or 0.0)
            highest_risk_band = str(q5c_summary.get("highest_risk_band") or "")
            watchlist_count = int(q5c_summary.get("watchlist_count") or 0)
            focus_text = (
                f" | focus {focus_metric}={focus_margin:.4f} @ {focus_package_id}"
                if focus_package_id and focus_metric
                else ""
            )
            risk_text = (
                f" | risk {highest_risk_band} | watch {watchlist_count}"
                if highest_risk_band
                else ""
            )
            self.q5c_quality_summary.setText(
                "Q5C-lite "
                f"{str(q5c_summary.get('status') or 'unknown').upper()} | "
                f"packages {int(q5c_summary.get('passing_package_count') or 0)}/{int(q5c_summary.get('package_count') or 0)} | "
                f"classes {classes_text}"
                f"{risk_text}"
                f"{focus_text}"
            )
            self.q5c_quality_summary.setVisible(True)
        self._render_q5c_contrast_focus()

    def _render_q5c_contrast_focus(self) -> None:
        contrast_focus = build_q5c_contrast_focus(
            self.app_state.quality_summaries,
            selected_package_id=self.view_state.selected_package_id,
        )
        if str(contrast_focus.get("status") or "missing") == "missing":
            self.q5c_contrast_summary.setVisible(False)
            self.q5c_contrast_summary.setText("")
            self.q5c_contrast_case_list.blockSignals(True)
            self.q5c_contrast_case_list.clear()
            self.q5c_contrast_case_list.blockSignals(False)
            self.q5c_contrast_case_list.setVisible(False)
            self.q5c_contrast_triptych.render_cases([])
            self.q5c_contrast_triptych.setVisible(False)
            self.q5c_contrast_compare_panel.render_compare_rows([])
            self.q5c_contrast_compare_panel.setVisible(False)
            return

        selected_package_id = str(contrast_focus.get("selected_package_id") or "")
        case_ids = [str(item) for item in list(contrast_focus.get("case_ids") or []) if str(item)]
        self.q5c_contrast_summary.setText(
            "Q5C contrast "
            f"{str(contrast_focus.get('status') or 'unknown').upper()} | "
            f"package {selected_package_id or 'n/a'} | "
            f"cases {', '.join(case_ids) if case_ids else 'none'}"
        )
        self.q5c_contrast_summary.setVisible(True)
        current_image_key = str(self.view_state.selected_image_key or "")
        recommended_image_key = str(contrast_focus.get("recommended_preview_image_key") or "")
        selected_case_key = current_image_key or recommended_image_key

        self.q5c_contrast_case_list.blockSignals(True)
        self.q5c_contrast_case_list.clear()
        for case in list(contrast_focus.get("cases") or []):
            case_id = str(case.get("case_id") or "")
            image_key = str(case.get("debug_image_key") or "")
            label = (
                f"{case_id} | {str(case.get('status') or '').upper()} | "
                f"{str(case.get('risk_band') or 'unknown')} | dz {float(case.get('delta_z') or 0.0):+.1f}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, image_key)
            self.q5c_contrast_case_list.addItem(item)
            if image_key and image_key == selected_case_key:
                self.q5c_contrast_case_list.setCurrentItem(item)
        if self.q5c_contrast_case_list.currentItem() is None and self.q5c_contrast_case_list.count():
            self.q5c_contrast_case_list.setCurrentRow(0)
        self.q5c_contrast_case_list.blockSignals(False)
        self.q5c_contrast_case_list.setVisible(self.q5c_contrast_case_list.count() > 0)
        self.q5c_contrast_triptych.render_cases(list(contrast_focus.get("cases") or []))
        self.q5c_contrast_triptych.setVisible(bool(list(contrast_focus.get("cases") or [])))
        self.q5c_contrast_compare_panel.render_compare_rows(
            list(contrast_focus.get("compare_rows") or []),
            summary_text=str(contrast_focus.get("compare_summary_text") or ""),
        )
        self.q5c_contrast_compare_panel.setVisible(bool(list(contrast_focus.get("compare_rows") or [])))

    def _render_report_tree(self) -> None:
        self.report_tree.clear()
        self.report_items_by_gate_id.clear()
        for category in CATEGORY_ORDER:
            records = list(self.app_state.report_categories.get(category) or [])
            parent = QTreeWidgetItem([CATEGORY_LABELS.get(category, category), str(len(records))])
            parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)
            self.report_tree.addTopLevelItem(parent)
            for record in records:
                child = QTreeWidgetItem([record.gate_id or record.name, record.status])
                child.setData(0, Qt.UserRole, record.gate_id)
                parent.addChild(child)
                if record.gate_id:
                    self.report_items_by_gate_id[record.gate_id] = child
            parent.setExpanded(True)
        self.report_tree.expandAll()
        if self.view_state.selected_report_gate_id:
            self._select_report(self.view_state.selected_report_gate_id)

    def _render_details(self) -> None:
        self.details_panel.render_report(self._selected_report_record())

    def _render_preview_images(self) -> None:
        self.images_panel.set_preview_records(
            list(self.app_state.preview_images),
            self.view_state.selected_image_key,
        )
        self._render_preview_image()

    def _render_preview_image(self) -> None:
        self.images_panel.render_selected_image(self._selected_preview_record())

    def _render_metrics(self) -> None:
        self.images_panel.render_metrics(list(self.app_state.r3_metrics))

    def _render_slot_table(self) -> None:
        self.slot_debugger_panel.render_slot_packages(list(self.app_state.slot_debugger.get("packages") or []))

    def _render_demo_session(self) -> None:
        session = self.app_state.demo_session
        self.demo_session_panel.render_session(
            session,
            self.view_state.selected_package_id or session.default_package_id,
        )
        self._render_demo_session_package_details()

    def _selected_demo_package_record(self) -> DemoPackageRecord | None:
        return self.app_state.demo_session.package_by_id(self.view_state.selected_package_id)

    def _render_demo_session_package_details(self) -> None:
        package = self._selected_demo_package_record()
        self.demo_session_panel.render_package_details(
            package,
            selected_action_preset_id=self.view_state.selected_action_preset_id,
            selected_animation_preset_id=self.view_state.selected_animation_preset_id,
        )
        self._render_demo_request()
        self._render_demo_review()

    def _render_demo_request(self) -> None:
        payload = self.current_dump_payload()
        demo_request = dict(payload.get("demo_request") or {})
        control_state = dict(payload.get("demo_request_control") or {})
        demo_control_state = dict(payload.get("demo_control_state") or {})
        demo_round_control = dict(payload.get("demo_round_control") or {})
        demo_round_state = dict(payload.get("demo_round_state") or {})
        workspace_path = str(self.current_workspace_config_path or "")
        workspace_ready = bool(self.current_workspace_config_path and Path(self.current_workspace_config_path).exists())
        self.demo_request_panel.render_request(
            demo_request,
            control_state,
            demo_control_state,
            demo_round_control,
            demo_round_state,
            workspace_path=workspace_path if workspace_ready else "",
        )

    def _render_demo_review(self) -> None:
        self.demo_review_focus = build_demo_review_focus(
            self.demo_review_state,
            selected_package_id=self.view_state.selected_package_id,
        )
        self.demo_review_history_focus = build_demo_review_history_focus(
            self.demo_review_history_state,
            selected_package_id=self.view_state.selected_package_id,
        )
        self.demo_review_compare_focus = build_demo_review_compare_focus(
            self.demo_review_compare_state,
            selected_package_id=self.view_state.selected_package_id,
            selected_pair_index=self.view_state.selected_review_compare_index,
        )
        self.demo_review_panel.render_review(
            dict(self.demo_review_state),
            dict(self.demo_review_focus),
            dict(self.demo_review_replay_state),
            dict(self.demo_review_replay_control),
            dict(self.demo_review_history_state),
            dict(self.demo_review_history_focus),
            dict(self.demo_review_compare_state),
            dict(self.demo_review_compare_focus),
            workspace_path=str(self.current_workspace_config_path or "")
            if self.current_workspace_config_path and Path(self.current_workspace_config_path).exists()
            else "",
            selected_package_id=self.view_state.selected_package_id,
        )

    def _refresh_demo_review_state(self, *, write: bool) -> None:
        session_manifest_path = self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path
        if write:
            self.demo_review_state = write_demo_review_state(
                session_manifest_path=session_manifest_path,
                demo_control_state=self.demo_control_state,
                demo_round_state=self.demo_round_state,
            )
        else:
            self.demo_review_state = build_demo_review_state(
                session_manifest_path=session_manifest_path,
                demo_control_state=self.demo_control_state,
                demo_round_state=self.demo_round_state,
            )
        self._render_demo_review()

    def _selected_report_record(self) -> ReportRecord | None:
        gate_id = self.view_state.selected_report_gate_id
        if not gate_id:
            return None
        return self.app_state.reports_by_gate_id.get(gate_id)

    def _selected_preview_record(self) -> PreviewImageRecord | None:
        image_key = self.view_state.selected_image_key
        return self.images_panel.preview_record(image_key)

    def _select_preview_image(self, image_key: str | None) -> None:
        if not image_key:
            return
        for index in range(self.preview_list.count()):
            item = self.preview_list.item(index)
            if str(item.data(Qt.UserRole) or "") == str(image_key):
                self.preview_list.setCurrentItem(item)
                self.view_state.selected_image_key = str(image_key)
                return

    def _on_report_selection_changed(self) -> None:
        selected_items = self.report_tree.selectedItems()
        if not selected_items:
            return
        gate_id = selected_items[0].data(0, Qt.UserRole)
        if not gate_id:
            return
        self.view_state.selected_report_gate_id = str(gate_id)
        self._render_details()

    def _on_preview_selection_changed(self) -> None:
        item = self.preview_list.currentItem()
        if item is None:
            return
        self.view_state.selected_image_key = str(item.data(Qt.UserRole) or "")
        self._render_preview_image()

    def _on_q5c_contrast_case_changed(self) -> None:
        item = self.q5c_contrast_case_list.currentItem()
        if item is None:
            return
        image_key = str(item.data(Qt.UserRole) or "")
        if not image_key:
            return
        self._select_preview_image(image_key)

    def _on_demo_session_package_changed(self) -> None:
        item = self.demo_session_package_list.currentItem()
        if item is None:
            return
        next_package_id = str(item.data(Qt.UserRole) or "")
        package_changed = next_package_id != str(self.view_state.selected_package_id or "")
        self.view_state.selected_package_id = next_package_id
        self.view_state.selected_action_preset_id = None
        self.view_state.selected_animation_preset_id = None
        if package_changed:
            self.view_state.selected_review_compare_index = 0
            contrast_focus = build_q5c_contrast_focus(
                self.app_state.quality_summaries,
                selected_package_id=next_package_id,
            )
            recommended_image_key = str(contrast_focus.get("recommended_preview_image_key") or "")
            if recommended_image_key:
                self.view_state.selected_image_key = recommended_image_key
        self._render_quality_summaries()
        self._render_preview_images()
        self._render_demo_session_package_details()

    def _on_demo_action_preset_changed(self) -> None:
        item = self.demo_action_preset_list.currentItem()
        if item is None:
            return
        self.view_state.selected_action_preset_id = str(item.data(Qt.UserRole) or "")
        self._render_demo_request()

    def _on_demo_animation_preset_changed(self) -> None:
        item = self.demo_animation_preset_list.currentItem()
        if item is None:
            return
        self.view_state.selected_animation_preset_id = str(item.data(Qt.UserRole) or "")
        self._render_demo_request()

    def _select_report(self, gate_id: str) -> None:
        item = self.report_items_by_gate_id.get(gate_id)
        if item is None:
            return
        self.report_tree.setCurrentItem(item)
        self.view_state.selected_report_gate_id = gate_id
        self._render_details()

    def _open_in_explorer(self, path: str) -> None:
        if not path:
            return
        target = Path(path)
        if target.is_file():
            subprocess.Popen(["explorer.exe", f"/select,{str(target)}"])
        else:
            subprocess.Popen(["explorer.exe", str(target)])

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._render_preview_image()
        self._render_q5c_contrast_focus()

    def export_current_state_json(self) -> str:
        return json.dumps(self.current_dump_payload(), ensure_ascii=False, indent=2)
