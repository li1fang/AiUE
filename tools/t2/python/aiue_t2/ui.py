from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aiue_t2.state import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    AppState,
    DemoPackageRecord,
    DemoRequestRecord,
    DemoSessionRecord,
    GovernanceBalanceRecord,
    ReportRecord,
    ViewState,
    build_default_view_state,
    load_workbench_state,
)
from aiue_t2.demo_control_state import load_demo_control_state, write_demo_control_run
from aiue_t2.demo_review_state import build_demo_review_focus, build_demo_review_state, write_demo_review_state
from aiue_t2.demo_review_replay_state import load_demo_review_replay_state, write_demo_review_replay_run
from aiue_t2.demo_round_state import load_demo_round_state, write_demo_round_state
from aiue_t2.demo_request_runner import export_demo_request, invoke_demo_request, load_demo_request_selection
from aiue_t2.ui_demo import DemoRequestControlState, DemoRequestPanel, DemoReviewPanel, DemoSessionPanel
from aiue_t2.ui_sections import DetailsPanel, ImagesPanel, SlotDebuggerPanel, SummaryCard


APP_STYLESHEET = """
QWidget {
    background: #0f172a;
    color: #e2e8f0;
    font-family: Segoe UI;
    font-size: 12px;
}
QMainWindow, QSplitter, QTabWidget::pane, QTreeWidget, QListWidget, QPlainTextEdit, QTableWidget {
    background: #0b1220;
}
QTreeWidget, QListWidget, QPlainTextEdit, QTableWidget {
    border: 1px solid #334155;
    border-radius: 8px;
}
QHeaderView::section {
    background: #1e293b;
    color: #cbd5e1;
    padding: 6px;
    border: 0;
}
QToolBar {
    border: 0;
    spacing: 8px;
}
QLabel[role="muted"] {
    color: #94a3b8;
}
QLabel[role="error"] {
    background: #3f1d1d;
    border: 1px solid #7f1d1d;
    border-radius: 8px;
    color: #fecaca;
    padding: 10px;
}
QFrame[card="true"] {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 12px;
}
"""

class WorkbenchWindow(QMainWindow):
    def __init__(
        self,
        *,
        manifest_path: Path,
        session_manifest_path: Path | None = None,
        repo_root: Path | None = None,
        workspace_config_path: Path | None = None,
        selected_package_id: str | None = None,
        selected_action_preset_id: str | None = None,
        selected_animation_preset_id: str | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("AiUE T2 Windows Native Workbench")
        self.resize(1440, 900)
        self.setStyleSheet(APP_STYLESHEET)
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.current_manifest_path = Path(manifest_path).expanduser().resolve()
        self.current_session_manifest_path = (
            Path(session_manifest_path).expanduser().resolve() if session_manifest_path is not None else None
        )
        self.current_workspace_config_path = self._resolve_workspace_config_path(workspace_config_path)
        self.requested_selected_package_id = selected_package_id
        self.requested_selected_action_preset_id = selected_action_preset_id
        self.requested_selected_animation_preset_id = selected_animation_preset_id
        self.app_state = AppState(
            status="error",
            manifest_path=str(self.current_manifest_path),
            pack_root=str(self.current_manifest_path.parent),
            generated_at_utc="",
            summary_counts={},
            report_categories={key: [] for key in CATEGORY_ORDER},
            reports_by_gate_id={},
            preview_images=[],
            r3_metrics=[],
            slot_debugger={"package_count": 0, "packages": []},
            governance_balance=GovernanceBalanceRecord(status="missing"),
            demo_session=DemoSessionRecord(
                status="missing",
                session_manifest_path="",
                session_id="",
                session_type="",
                host_key="",
                mode="",
                level_path="",
                default_package_id=None,
            ),
            demo_request=DemoRequestRecord(
                status="missing",
                selected_package_id=None,
                selected_action_preset_id=None,
                selected_animation_preset_id=None,
            ),
            errors=[],
            default_report_gate_id=None,
            default_image_key=None,
            default_package_id=None,
            default_action_preset_id=None,
            default_animation_preset_id=None,
        )
        self.view_state = ViewState()
        self.demo_control_state: dict = {"status": "missing", "last_runs_by_package": {}, "package_run_counts": {}}
        self.demo_round_state: dict = {"status": "missing", "package_results": [], "counts": {}}
        self.demo_review_state: dict = {"status": "missing", "package_reviews": [], "summary": {}}
        self.demo_review_focus: dict = {"status": "missing", "selected_package_id": ""}
        self.demo_review_replay_state: dict = {"status": "missing", "last_replays_by_package": {}, "package_replay_counts": {}}
        self.demo_review_replay_control: dict = {"status": "idle", "operation": "", "request_kind": "", "errors": []}
        self.demo_round_control: dict = {"status": "idle", "operation": "", "scope": "", "errors": []}
        self.demo_request_control = DemoRequestControlState(
            workspace_config_path=str(self.current_workspace_config_path or ""),
        )
        self.report_items_by_gate_id: dict[str, QTreeWidgetItem] = {}
        self._build_ui()
        self.load_manifest(self.current_manifest_path, session_manifest_path=self.current_session_manifest_path)

    def _build_ui(self) -> None:
        toolbar = QToolBar("Workbench")
        self.addToolBar(toolbar)
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_from_manifest)
        toolbar.addAction(refresh_action)

        choose_manifest_action = QAction("Choose Manifest", self)
        choose_manifest_action.triggered.connect(self.choose_manifest)
        toolbar.addAction(choose_manifest_action)

        open_report_action = QAction("Open Report", self)
        open_report_action.triggered.connect(self.open_selected_report)
        toolbar.addAction(open_report_action)

        open_image_action = QAction("Open Image", self)
        open_image_action.triggered.connect(self.open_selected_image)
        toolbar.addAction(open_image_action)

        open_pack_action = QAction("Open Pack Root", self)
        open_pack_action.triggered.connect(self.open_pack_root)
        toolbar.addAction(open_pack_action)

        open_session_action = QAction("Open Session", self)
        open_session_action.triggered.connect(self.open_demo_session_manifest)
        toolbar.addAction(open_session_action)

        root = QWidget()
        root_layout = QVBoxLayout(root)

        self.error_banner = QLabel("")
        self.error_banner.setProperty("role", "error")
        self.error_banner.setVisible(False)
        self.error_banner.setWordWrap(True)
        root_layout.addWidget(self.error_banner)

        summary_layout = QHBoxLayout()
        self.summary_cards = {
            "reports": SummaryCard(title="Reports", object_name="summaryReportsCard"),
            "active": SummaryCard(title="Active Line", object_name="summaryActiveCard"),
            "platform": SummaryCard(title="Platform Line", object_name="summaryPlatformCard"),
            "governance": SummaryCard(title="Governance Line", object_name="summaryGovernanceCard"),
            "passing": SummaryCard(title="Passing", object_name="summaryPassingCard"),
        }
        for card in self.summary_cards.values():
            summary_layout.addWidget(card)
        root_layout.addLayout(summary_layout)

        content_splitter = QSplitter()

        self.report_tree = QTreeWidget()
        self.report_tree.setObjectName("reportTree")
        self.report_tree.setHeaderLabels(["Report", "Status"])
        self.report_tree.itemSelectionChanged.connect(self._on_report_selection_changed)
        content_splitter.addWidget(self.report_tree)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("contentTabs")

        self.details_panel = DetailsPanel()
        self.details_header = self.details_panel.details_header
        self.details_text = self.details_panel.details_text
        self.tabs.addTab(self.details_panel, "Details")

        self.images_panel = ImagesPanel()
        self.preview_list = self.images_panel.preview_list
        self.preview_list.currentItemChanged.connect(self._on_preview_selection_changed)
        self.preview_label = self.images_panel.preview_label
        self.metrics_table = self.images_panel.metrics_table
        self.tabs.addTab(self.images_panel, "Images")

        self.slot_debugger_panel = SlotDebuggerPanel()
        self.slot_table = self.slot_debugger_panel.slot_table
        self.tabs.addTab(self.slot_debugger_panel, "Slot Debugger")

        self.demo_session_panel = DemoSessionPanel()
        self.demo_session_summary = self.demo_session_panel.demo_session_summary
        self.demo_session_package_list = self.demo_session_panel.demo_session_package_list
        self.demo_session_package_list.currentItemChanged.connect(self._on_demo_session_package_changed)
        self.demo_action_preset_list = self.demo_session_panel.demo_action_preset_list
        self.demo_action_preset_list.currentItemChanged.connect(self._on_demo_action_preset_changed)
        self.demo_animation_preset_list = self.demo_session_panel.demo_animation_preset_list
        self.demo_animation_preset_list.currentItemChanged.connect(self._on_demo_animation_preset_changed)
        self.demo_package_details = self.demo_session_panel.demo_package_details
        self.tabs.addTab(self.demo_session_panel, "Demo Session")

        self.demo_request_panel = DemoRequestPanel()
        self.demo_request_summary = self.demo_request_panel.demo_request_summary
        self.demo_request_workspace = self.demo_request_panel.demo_request_workspace
        self.export_action_request_button = self.demo_request_panel.export_action_request_button
        self.export_animation_request_button = self.demo_request_panel.export_animation_request_button
        self.dry_run_action_request_button = self.demo_request_panel.dry_run_action_request_button
        self.dry_run_animation_request_button = self.demo_request_panel.dry_run_animation_request_button
        self.invoke_action_request_button = self.demo_request_panel.invoke_action_request_button
        self.invoke_animation_request_button = self.demo_request_panel.invoke_animation_request_button
        self.invoke_session_round_button = self.demo_request_panel.invoke_session_round_button
        self.demo_request_control_summary = self.demo_request_panel.demo_request_control_summary
        self.demo_control_state_summary = self.demo_request_panel.demo_control_state_summary
        self.demo_request_text = self.demo_request_panel.demo_request_text
        self.demo_request_control_text = self.demo_request_panel.demo_request_control_text
        self.demo_control_state_text = self.demo_request_panel.demo_control_state_text
        self.demo_request_panel.bind_callbacks(
            export_action=lambda: self.export_current_demo_request(request_kind="action_preview"),
            export_animation=lambda: self.export_current_demo_request(request_kind="animation_preview"),
            dry_run_action=lambda: self.dry_run_current_demo_request(request_kind="action_preview"),
            dry_run_animation=lambda: self.dry_run_current_demo_request(request_kind="animation_preview"),
            invoke_action=lambda: self.invoke_current_demo_request(request_kind="action_preview"),
            invoke_animation=lambda: self.invoke_current_demo_request(request_kind="animation_preview"),
            invoke_session_round=lambda: self.invoke_session_round(),
        )
        self.tabs.addTab(self.demo_request_panel, "Demo Request")

        self.demo_review_panel = DemoReviewPanel()
        self.demo_review_summary = self.demo_review_panel.demo_review_summary
        self.demo_review_package_summary = self.demo_review_panel.demo_review_package_summary
        self.demo_review_text = self.demo_review_panel.demo_review_text
        self.open_review_artifact_button = self.demo_review_panel.open_review_artifact_button
        self.open_hero_before_button = self.demo_review_panel.open_hero_before_button
        self.open_action_after_button = self.demo_review_panel.open_action_after_button
        self.open_animation_after_button = self.demo_review_panel.open_animation_after_button
        self.replay_action_button = self.demo_review_panel.replay_action_button
        self.replay_animation_button = self.demo_review_panel.replay_animation_button
        self.demo_review_replay_summary = self.demo_review_panel.demo_review_replay_summary
        self.demo_review_panel.bind_callbacks(
            open_review_artifact=lambda: self.open_demo_review_artifact(),
            open_hero_before=lambda: self.open_demo_review_hero_before(),
            open_action_after=lambda: self.open_demo_review_action_after(),
            open_animation_after=lambda: self.open_demo_review_animation_after(),
            replay_action=lambda: self.replay_current_demo_review(request_kind="action_preview"),
            replay_animation=lambda: self.replay_current_demo_review(request_kind="animation_preview"),
        )
        self.tabs.addTab(self.demo_review_panel, "Demo Review")

        content_splitter.addWidget(self.tabs)
        content_splitter.setStretchFactor(1, 1)
        root_layout.addWidget(content_splitter)

        self.setCentralWidget(root)

    def load_manifest(self, manifest_path: Path, *, session_manifest_path: Path | None = None) -> None:
        self.current_manifest_path = Path(manifest_path).expanduser().resolve()
        self.current_session_manifest_path = (
            Path(session_manifest_path).expanduser().resolve() if session_manifest_path is not None else self.current_session_manifest_path
        )
        self.app_state = load_workbench_state(
            self.current_manifest_path,
            session_manifest_path=self.current_session_manifest_path,
        )
        self.view_state = build_default_view_state(self.app_state)
        self._apply_requested_demo_selection()
        self.demo_control_state = load_demo_control_state(
            self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path
        )
        self.demo_round_state = load_demo_round_state(
            self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path
        )
        self.demo_review_state = build_demo_review_state(
            session_manifest_path=self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path,
            demo_control_state=self.demo_control_state,
            demo_round_state=self.demo_round_state,
        )
        self.demo_review_focus = build_demo_review_focus(
            self.demo_review_state,
            selected_package_id=self.view_state.selected_package_id,
        )
        self.demo_review_replay_state = load_demo_review_replay_state(
            self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path
        )
        self.demo_review_replay_control = {"status": "idle", "operation": "", "request_kind": "", "errors": []}
        self.demo_round_control = {"status": "idle", "operation": "", "scope": "", "errors": []}
        self.demo_request_control = DemoRequestControlState(
            workspace_config_path=str(self.current_workspace_config_path or ""),
        )
        self._render_state()

    def _resolve_workspace_config_path(self, workspace_config_path: Path | None = None) -> Path | None:
        if workspace_config_path is not None:
            return Path(workspace_config_path).expanduser().resolve()
        default_path = self.repo_root / "local" / "pipeline_workspace.local.json"
        return default_path.resolve() if default_path.exists() else None

    def refresh_from_manifest(self) -> None:
        self.load_manifest(self.current_manifest_path)

    def _apply_requested_demo_selection(self) -> None:
        package_ids = {record.package_id for record in self.app_state.demo_session.packages}
        if self.requested_selected_package_id and self.requested_selected_package_id in package_ids:
            self.view_state.selected_package_id = self.requested_selected_package_id
        selected_package = self.app_state.demo_session.package_by_id(self.view_state.selected_package_id)
        if selected_package is None:
            return
        action_preset_ids = {preset.preset_id for preset in selected_package.action_presets}
        animation_preset_ids = {preset.preset_id for preset in selected_package.animation_presets}
        if self.requested_selected_action_preset_id and self.requested_selected_action_preset_id in action_preset_ids:
            self.view_state.selected_action_preset_id = self.requested_selected_action_preset_id
        if self.requested_selected_animation_preset_id and self.requested_selected_animation_preset_id in animation_preset_ids:
            self.view_state.selected_animation_preset_id = self.requested_selected_animation_preset_id

    def choose_manifest(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose T1 manifest",
            str(self.current_manifest_path.parent),
            "JSON Files (*.json)",
        )
        if path:
            self.load_manifest(Path(path))

    def current_dump_payload(self) -> dict:
        payload = self.app_state.to_dump_payload(self.view_state)
        payload["demo_control_state"] = dict(self.demo_control_state)
        payload["demo_round_state"] = dict(self.demo_round_state)
        payload["demo_review_state"] = dict(self.demo_review_state)
        payload["demo_review_focus"] = dict(self.demo_review_focus)
        payload["demo_review_replay_state"] = dict(self.demo_review_replay_state)
        payload["demo_review_replay_control"] = dict(self.demo_review_replay_control)
        payload["demo_round_control"] = dict(self.demo_round_control)
        payload["demo_request_control"] = self.demo_request_control.to_dump_dict()
        return payload

    def current_error_codes(self) -> list[str]:
        return [error.code for error in self.app_state.errors]

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

    def open_demo_session_manifest(self) -> None:
        session_manifest_path = self.app_state.demo_session.session_manifest_path
        if session_manifest_path:
            self._open_in_explorer(session_manifest_path)

    def open_demo_review_artifact(self) -> None:
        self._open_in_explorer(str(self.demo_review_focus.get("review_state_path") or self.demo_review_state.get("review_state_path") or ""))

    def open_demo_review_hero_before(self) -> None:
        self._open_in_explorer(str(self.demo_review_focus.get("hero_before_image_path") or ""))

    def open_demo_review_action_after(self) -> None:
        self._open_in_explorer(str(self.demo_review_focus.get("action_primary_after_image_path") or ""))

    def open_demo_review_animation_after(self) -> None:
        self._open_in_explorer(str(self.demo_review_focus.get("animation_primary_after_image_path") or ""))

    def replay_current_demo_review(
        self,
        *,
        request_kind: str,
        workspace_config_path: Path | None = None,
    ) -> None:
        resolved_workspace = (
            Path(workspace_config_path).expanduser().resolve()
            if workspace_config_path is not None
            else (self.current_workspace_config_path or self._resolve_workspace_config_path(None))
        )
        if resolved_workspace is None or not resolved_workspace.exists():
            self.demo_review_replay_control = {
                "status": "error",
                "operation": "review_replay",
                "request_kind": str(request_kind or ""),
                "workspace_config_path": str(resolved_workspace or ""),
                "errors": ["workspace_config_missing"],
            }
            self._render_demo_review()
            return
        if str(self.demo_review_focus.get("status") or "") != "pass":
            self.demo_review_replay_control = {
                "status": "error",
                "operation": "review_replay",
                "request_kind": str(request_kind or ""),
                "workspace_config_path": str(resolved_workspace),
                "errors": ["review_focus_not_ready"],
            }
            self._render_demo_review()
            return
        self.current_workspace_config_path = resolved_workspace
        try:
            selection = load_demo_request_selection(
                **self._selected_demo_request_kwargs(),
                request_kind=request_kind,
            )
            invocation = invoke_demo_request(
                selection,
                workspace_config=resolved_workspace,
                dry_run=False,
            )
            invocation_payload = dict(invocation.get("payload") or {})
            invocation_result = dict(invocation_payload.get("result") or {})
            invocation_meta = dict(invocation.get("invocation") or {})
            self.demo_control_state = write_demo_control_run(
                session_manifest_path=self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path,
                session_id=self.app_state.demo_session.session_id,
                selected_package_id=selection.selected_package_id,
                selected_action_preset_id=selection.selected_action_preset_id,
                selected_animation_preset_id=selection.selected_animation_preset_id,
                request_kind=selection.request_kind,
                operation="review_replay",
                invocation=invocation,
            )
            self.demo_review_replay_state = write_demo_review_replay_run(
                session_manifest_path=self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path,
                source_review_state_path=str(self.demo_review_state.get("review_state_path") or ""),
                session_id=self.app_state.demo_session.session_id,
                selected_package_id=selection.selected_package_id,
                selected_action_preset_id=selection.selected_action_preset_id,
                selected_animation_preset_id=selection.selected_animation_preset_id,
                request_kind=selection.request_kind,
                invocation=invocation,
            )
            self._refresh_demo_review_state(write=False)
            result_status = str(invocation_result.get("status") or invocation_payload.get("status") or "")
            self.demo_review_replay_control = {
                "status": "pass" if result_status == "pass" else "error",
                "operation": "review_replay",
                "request_kind": selection.request_kind,
                "workspace_config_path": str(resolved_workspace),
                "request_json_path": str(invocation.get("request_json_path") or ""),
                "result_json_path": str(invocation.get("result_json_path") or ""),
                "host_key": str(invocation.get("host_key") or ""),
                "result_status": result_status,
                "invocation_returncode": invocation_meta.get("returncode"),
                "errors": [],
            }
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.demo_review_replay_control = {
                "status": "error",
                "operation": "review_replay",
                "request_kind": str(request_kind or ""),
                "workspace_config_path": str(resolved_workspace),
                "errors": [str(exc)],
            }
        self._render_demo_request()
        self._render_demo_review()

    def _selected_demo_request_kwargs(self) -> dict:
        return {
            "repo_root": self.repo_root,
            "manifest_path": self.current_manifest_path,
            "session_manifest_path": self.current_session_manifest_path,
            "package_id": self.view_state.selected_package_id,
            "action_preset_id": self.view_state.selected_action_preset_id,
            "animation_preset_id": self.view_state.selected_animation_preset_id,
        }

    def export_current_demo_request(self, *, request_kind: str = "action_preview") -> None:
        try:
            selection = load_demo_request_selection(
                **self._selected_demo_request_kwargs(),
                request_kind=request_kind,
            )
            exported_path = export_demo_request(selection)
            self.demo_request_control = DemoRequestControlState(
                status="pass",
                operation="export",
                request_kind=selection.request_kind,
                workspace_config_path=str(self.current_workspace_config_path or ""),
                request_json_path=str(exported_path),
                payload=selection.to_dump_dict(),
            )
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.demo_request_control = DemoRequestControlState(
                status="error",
                operation="export",
                request_kind=str(request_kind or ""),
                workspace_config_path=str(self.current_workspace_config_path or ""),
                errors=[str(exc)],
            )
        self._render_demo_request()

    def _execute_current_demo_request(
        self,
        *,
        request_kind: str,
        dry_run: bool,
        workspace_config_path: Path | None = None,
    ) -> None:
        resolved_workspace = (
            Path(workspace_config_path).expanduser().resolve()
            if workspace_config_path is not None
            else (self.current_workspace_config_path or self._resolve_workspace_config_path(None))
        )
        operation_name = "dry_run" if dry_run else "invoke"
        if resolved_workspace is None or not resolved_workspace.exists():
            self.demo_request_control = DemoRequestControlState(
                status="error",
                operation=operation_name,
                request_kind=str(request_kind or ""),
                dry_run=bool(dry_run),
                workspace_config_path=str(resolved_workspace or ""),
                errors=["workspace_config_missing"],
            )
            self._render_demo_request()
            return
        self.current_workspace_config_path = resolved_workspace
        try:
            selection = load_demo_request_selection(
                **self._selected_demo_request_kwargs(),
                request_kind=request_kind,
            )
            invocation = invoke_demo_request(
                selection,
                workspace_config=resolved_workspace,
                dry_run=dry_run,
            )
            invocation_payload = dict(invocation.get("payload") or {})
            invocation_result = dict(invocation_payload.get("result") or {})
            invocation_meta = dict(invocation.get("invocation") or {})
            self.demo_control_state = write_demo_control_run(
                session_manifest_path=self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path,
                session_id=self.app_state.demo_session.session_id,
                selected_package_id=selection.selected_package_id,
                selected_action_preset_id=selection.selected_action_preset_id,
                selected_animation_preset_id=selection.selected_animation_preset_id,
                request_kind=selection.request_kind,
                operation=operation_name,
                invocation=invocation,
            )
            result_status = str(invocation_result.get("status") or invocation_payload.get("status") or "")
            self.demo_request_control = DemoRequestControlState(
                status="pass" if result_status == "pass" else "error",
                operation=operation_name,
                request_kind=selection.request_kind,
                dry_run=bool(dry_run),
                workspace_config_path=str(resolved_workspace),
                request_json_path=str(invocation.get("request_json_path") or ""),
                result_json_path=str(invocation.get("result_json_path") or ""),
                host_key=str(invocation.get("host_key") or ""),
                result_status=result_status,
                invocation_returncode=invocation_meta.get("returncode"),
                payload=invocation,
            )
            self._refresh_demo_review_state(write=not dry_run)
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.demo_request_control = DemoRequestControlState(
                status="error",
                operation=operation_name,
                request_kind=str(request_kind or ""),
                dry_run=bool(dry_run),
                workspace_config_path=str(resolved_workspace),
                errors=[str(exc)],
            )
        self._render_demo_request()

    def dry_run_current_demo_request(
        self,
        *,
        request_kind: str = "action_preview",
        workspace_config_path: Path | None = None,
    ) -> None:
        self._execute_current_demo_request(
            request_kind=request_kind,
            dry_run=True,
            workspace_config_path=workspace_config_path,
        )

    def invoke_current_demo_request(
        self,
        *,
        request_kind: str = "action_preview",
        workspace_config_path: Path | None = None,
    ) -> None:
        self._execute_current_demo_request(
            request_kind=request_kind,
            dry_run=False,
            workspace_config_path=workspace_config_path,
        )

    @staticmethod
    def _first_preset_id(presets: list) -> str | None:
        if not presets:
            return None
        return str(presets[0].preset_id or "") or None

    def _build_round_package_result(self, package_id: str) -> dict:
        package_runs = dict((self.demo_control_state.get("last_runs_by_package") or {}).get(package_id) or {})
        action_invoke = dict(package_runs.get("action_preview") or {})
        animation_invoke = dict(package_runs.get("animation_preview") or {})
        errors: list[dict] = []
        if not action_invoke:
            errors.append({"id": "round_action_missing", "message": "The session round did not capture an action_preview run."})
        if not animation_invoke:
            errors.append({"id": "round_animation_missing", "message": "The session round did not capture an animation_preview run."})
        if action_invoke and str(action_invoke.get("result_status") or "") != "pass":
            errors.append({"id": "round_action_failed", "message": "The session round action_preview result did not pass."})
        if animation_invoke and str(animation_invoke.get("result_status") or "") != "pass":
            errors.append({"id": "round_animation_failed", "message": "The session round animation_preview result did not pass."})
        action_credibility = dict(action_invoke.get("credibility_summary") or {})
        animation_credibility = dict(animation_invoke.get("credibility_summary") or {})
        if action_invoke and not bool(action_credibility.get("action_motion_verified")):
            errors.append({"id": "round_action_motion_not_verified", "message": "The session round action_preview credibility check did not verify motion."})
        if animation_invoke and not bool(animation_credibility.get("animation_pose_verified")):
            errors.append({"id": "round_animation_pose_not_verified", "message": "The session round animation_preview credibility check did not verify pose change."})
        return {
            "package_id": package_id,
            "selected_action_preset_id": action_invoke.get("selected_action_preset_id"),
            "selected_animation_preset_id": animation_invoke.get("selected_animation_preset_id"),
            "action_invoke": action_invoke,
            "animation_invoke": animation_invoke,
            "status": "pass" if not errors else "fail",
            "errors": errors,
        }

    def invoke_session_round(self, *, workspace_config_path: Path | None = None) -> None:
        resolved_workspace = (
            Path(workspace_config_path).expanduser().resolve()
            if workspace_config_path is not None
            else (self.current_workspace_config_path or self._resolve_workspace_config_path(None))
        )
        if resolved_workspace is None or not resolved_workspace.exists():
            self.demo_round_control = {
                "status": "error",
                "operation": "invoke_session_round",
                "scope": "full_session",
                "workspace_config_path": str(resolved_workspace or ""),
                "errors": ["workspace_config_missing"],
            }
            self._render_demo_request()
            return
        self.current_workspace_config_path = resolved_workspace
        previous_selection = (
            self.view_state.selected_package_id,
            self.view_state.selected_action_preset_id,
            self.view_state.selected_animation_preset_id,
        )
        package_results: list[dict] = []
        round_errors: list[str] = []
        try:
            for package in self.app_state.demo_session.packages:
                action_preset_id = self._first_preset_id(package.action_presets)
                animation_preset_id = self._first_preset_id(package.animation_presets)
                if not action_preset_id or not animation_preset_id:
                    round_errors.append(f"missing_presets:{package.package_id}")
                    package_results.append(
                        {
                            "package_id": package.package_id,
                            "selected_action_preset_id": action_preset_id,
                            "selected_animation_preset_id": animation_preset_id,
                            "action_invoke": {},
                            "animation_invoke": {},
                            "status": "fail",
                            "errors": [{"id": "round_presets_missing", "message": "The package does not have both action and animation presets."}],
                        }
                    )
                    continue
                self.view_state.selected_package_id = package.package_id
                self.view_state.selected_action_preset_id = action_preset_id
                self.view_state.selected_animation_preset_id = animation_preset_id
                self._render_demo_session_package_details()
                self._execute_current_demo_request(
                    request_kind="action_preview",
                    dry_run=False,
                    workspace_config_path=resolved_workspace,
                )
                self._execute_current_demo_request(
                    request_kind="animation_preview",
                    dry_run=False,
                    workspace_config_path=resolved_workspace,
                )
                package_results.append(self._build_round_package_result(package.package_id))
            self.demo_round_state = write_demo_round_state(
                session_manifest_path=self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path,
                session_id=self.app_state.demo_session.session_id,
                operation="invoke_session_round",
                package_results=package_results,
            )
            self._refresh_demo_review_state(write=True)
            round_status = "pass" if self.demo_round_state.get("status") == "pass" and not round_errors else "error"
            self.demo_round_control = {
                "status": round_status,
                "operation": "invoke_session_round",
                "scope": "full_session",
                "workspace_config_path": str(resolved_workspace),
                "package_count": len(package_results),
                "round_state_path": self.demo_round_state.get("round_state_path"),
                "errors": round_errors,
            }
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.demo_round_control = {
                "status": "error",
                "operation": "invoke_session_round",
                "scope": "full_session",
                "workspace_config_path": str(resolved_workspace),
                "errors": [str(exc)],
            }
        finally:
            (
                self.view_state.selected_package_id,
                self.view_state.selected_action_preset_id,
                self.view_state.selected_animation_preset_id,
            ) = previous_selection
            self._render_demo_session_package_details()

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
        self.demo_review_panel.render_review(
            dict(self.demo_review_state),
            dict(self.demo_review_focus),
            dict(self.demo_review_replay_state),
            dict(self.demo_review_replay_control),
            workspace_path=str(self.current_workspace_config_path or "") if self.current_workspace_config_path and Path(self.current_workspace_config_path).exists() else "",
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
