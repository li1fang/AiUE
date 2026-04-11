from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

from aiue_t2.demo_review_history_state import build_demo_review_history_focus
from aiue_t2.demo_review_state import build_demo_review_focus, build_demo_review_state, write_demo_review_state
from aiue_t2.state import CATEGORY_LABELS, CATEGORY_ORDER, DemoPackageRecord, PreviewImageRecord, ReportRecord


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
        self.summary_cards["governance"].set_value(int(counts.get("governance_line_reports") or 0))
        self.summary_cards["passing"].set_value(int(counts.get("passing_reports") or 0))
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
        self.demo_review_panel.render_review(
            dict(self.demo_review_state),
            dict(self.demo_review_focus),
            dict(self.demo_review_replay_state),
            dict(self.demo_review_replay_control),
            dict(self.demo_review_history_state),
            dict(self.demo_review_history_focus),
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

    def _on_demo_session_package_changed(self) -> None:
        item = self.demo_session_package_list.currentItem()
        if item is None:
            return
        self.view_state.selected_package_id = str(item.data(Qt.UserRole) or "")
        self.view_state.selected_action_preset_id = None
        self.view_state.selected_animation_preset_id = None
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

    def export_current_state_json(self) -> str:
        return json.dumps(self.current_dump_payload(), ensure_ascii=False, indent=2)
