from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
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
    DemoPresetRecord,
    DemoRequestRecord,
    DemoSessionRecord,
    GovernanceBalanceRecord,
    PreviewImageRecord,
    ReportRecord,
    ViewState,
    build_default_view_state,
    load_workbench_state,
    report_payload_to_text,
)
from aiue_t2.demo_request_runner import export_demo_request, invoke_demo_request, load_demo_request_selection


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


@dataclass
class DemoRequestControlState:
    status: str = "idle"
    operation: str = ""
    request_kind: str = ""
    dry_run: bool = False
    workspace_config_path: str = ""
    request_json_path: str = ""
    result_json_path: str = ""
    host_key: str = ""
    result_status: str = ""
    invocation_returncode: int | None = None
    errors: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)

    def to_dump_dict(self) -> dict:
        return {
            "status": self.status,
            "operation": self.operation,
            "request_kind": self.request_kind,
            "dry_run": self.dry_run,
            "workspace_config_path": self.workspace_config_path,
            "request_json_path": self.request_json_path,
            "result_json_path": self.result_json_path,
            "host_key": self.host_key,
            "result_status": self.result_status,
            "invocation_returncode": self.invocation_returncode,
            "errors": list(self.errors),
            "payload": dict(self.payload),
        }


class SummaryCard(QFrame):
    def __init__(self, *, title: str, object_name: str) -> None:
        super().__init__()
        self.setObjectName(object_name)
        self.setProperty("card", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        title_label = QLabel(title)
        title_label.setProperty("role", "muted")
        self.value_label = QLabel("0")
        self.value_label.setObjectName(f"{object_name}Value")
        self.value_label.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class WorkbenchWindow(QMainWindow):
    def __init__(
        self,
        *,
        manifest_path: Path,
        session_manifest_path: Path | None = None,
        repo_root: Path | None = None,
        workspace_config_path: Path | None = None,
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
        self.demo_request_control = DemoRequestControlState(
            workspace_config_path=str(self.current_workspace_config_path or ""),
        )
        self.report_items_by_gate_id: dict[str, QTreeWidgetItem] = {}
        self.preview_records_by_key: dict[str, PreviewImageRecord] = {}
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

        self.details_header = QLabel("No report selected")
        self.details_header.setProperty("role", "muted")
        self.details_text = QPlainTextEdit()
        self.details_text.setObjectName("detailsJsonText")
        self.details_text.setReadOnly(True)
        details_root = QWidget()
        details_layout = QVBoxLayout(details_root)
        details_layout.addWidget(self.details_header)
        details_layout.addWidget(self.details_text)
        self.tabs.addTab(details_root, "Details")

        self.preview_list = QListWidget()
        self.preview_list.setObjectName("previewImageList")
        self.preview_list.currentItemChanged.connect(self._on_preview_selection_changed)
        self.preview_label = QLabel("No preview image selected")
        self.preview_label.setObjectName("previewImageLabel")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(320)
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("border: 1px solid #334155; border-radius: 8px;")

        preview_splitter = QSplitter()
        preview_splitter.addWidget(self.preview_list)
        preview_splitter.addWidget(self.preview_label)

        self.metrics_table = QTableWidget(0, 7)
        self.metrics_table.setObjectName("r3MetricsTable")
        self.metrics_table.setHorizontalHeaderLabels(
            [
                "Package",
                "Shot",
                "Status",
                "Crop Hist L1",
                "Crop Mean Delta",
                "Full Hist L1",
                "Full Mean Delta",
            ]
        )
        self.metrics_table.horizontalHeader().setStretchLastSection(True)

        images_root = QWidget()
        images_layout = QVBoxLayout(images_root)
        images_layout.addWidget(preview_splitter)
        metrics_box = QGroupBox("Before / After Metrics")
        metrics_layout = QVBoxLayout(metrics_box)
        metrics_layout.addWidget(self.metrics_table)
        images_layout.addWidget(metrics_box)
        self.tabs.addTab(images_root, "Images")

        self.slot_table = QTableWidget(0, 8)
        self.slot_table.setObjectName("slotDebuggerTable")
        self.slot_table.setHorizontalHeaderLabels(
            [
                "Package",
                "Slot",
                "Kind",
                "Component",
                "Socket",
                "Coverages",
                "Conflicts",
                "Superseded",
            ]
        )
        self.slot_table.horizontalHeader().setStretchLastSection(True)
        slot_root = QWidget()
        slot_layout = QVBoxLayout(slot_root)
        slot_layout.addWidget(self.slot_table)
        self.tabs.addTab(slot_root, "Slot Debugger")

        self.demo_session_summary = QLabel("No E2 session loaded")
        self.demo_session_summary.setObjectName("demoSessionSummaryLabel")
        self.demo_session_summary.setProperty("role", "muted")
        self.demo_session_summary.setWordWrap(True)

        self.demo_session_package_list = QListWidget()
        self.demo_session_package_list.setObjectName("demoSessionPackageList")
        self.demo_session_package_list.currentItemChanged.connect(self._on_demo_session_package_changed)

        self.demo_action_preset_list = QListWidget()
        self.demo_action_preset_list.setObjectName("demoActionPresetList")
        self.demo_action_preset_list.currentItemChanged.connect(self._on_demo_action_preset_changed)

        self.demo_animation_preset_list = QListWidget()
        self.demo_animation_preset_list.setObjectName("demoAnimationPresetList")
        self.demo_animation_preset_list.currentItemChanged.connect(self._on_demo_animation_preset_changed)

        self.demo_package_details = QPlainTextEdit()
        self.demo_package_details.setObjectName("demoPackageDetailsText")
        self.demo_package_details.setReadOnly(True)

        action_box = QGroupBox("Action Presets")
        action_box_layout = QVBoxLayout(action_box)
        action_box_layout.addWidget(self.demo_action_preset_list)

        animation_box = QGroupBox("Animation Presets")
        animation_box_layout = QVBoxLayout(animation_box)
        animation_box_layout.addWidget(self.demo_animation_preset_list)

        session_right = QWidget()
        session_right_layout = QVBoxLayout(session_right)
        session_right_layout.addWidget(self.demo_session_summary)
        session_right_layout.addWidget(action_box)
        session_right_layout.addWidget(animation_box)
        session_right_layout.addWidget(self.demo_package_details)

        session_splitter = QSplitter()
        session_splitter.addWidget(self.demo_session_package_list)
        session_splitter.addWidget(session_right)
        session_splitter.setStretchFactor(0, 0)
        session_splitter.setStretchFactor(1, 1)

        demo_root = QWidget()
        demo_layout = QVBoxLayout(demo_root)
        demo_layout.addWidget(session_splitter)
        self.tabs.addTab(demo_root, "Demo Session")

        self.demo_request_summary = QLabel("No demo request selected")
        self.demo_request_summary.setObjectName("demoRequestSummaryLabel")
        self.demo_request_summary.setProperty("role", "muted")
        self.demo_request_summary.setWordWrap(True)

        self.demo_request_workspace = QLabel("Workspace config: not configured")
        self.demo_request_workspace.setObjectName("demoRequestWorkspaceLabel")
        self.demo_request_workspace.setProperty("role", "muted")
        self.demo_request_workspace.setWordWrap(True)

        self.export_action_request_button = QPushButton("Export Action Request")
        self.export_action_request_button.setObjectName("exportActionRequestButton")
        self.export_action_request_button.clicked.connect(
            lambda: self.export_current_demo_request(request_kind="action_preview")
        )

        self.export_animation_request_button = QPushButton("Export Animation Request")
        self.export_animation_request_button.setObjectName("exportAnimationRequestButton")
        self.export_animation_request_button.clicked.connect(
            lambda: self.export_current_demo_request(request_kind="animation_preview")
        )

        self.dry_run_action_request_button = QPushButton("Dry Run Action Request")
        self.dry_run_action_request_button.setObjectName("dryRunActionRequestButton")
        self.dry_run_action_request_button.clicked.connect(
            lambda: self.dry_run_current_demo_request(request_kind="action_preview")
        )

        self.dry_run_animation_request_button = QPushButton("Dry Run Animation Request")
        self.dry_run_animation_request_button.setObjectName("dryRunAnimationRequestButton")
        self.dry_run_animation_request_button.clicked.connect(
            lambda: self.dry_run_current_demo_request(request_kind="animation_preview")
        )

        self.invoke_action_request_button = QPushButton("Invoke Action Request")
        self.invoke_action_request_button.setObjectName("invokeActionRequestButton")
        self.invoke_action_request_button.clicked.connect(
            lambda: self.invoke_current_demo_request(request_kind="action_preview")
        )

        self.invoke_animation_request_button = QPushButton("Invoke Animation Request")
        self.invoke_animation_request_button.setObjectName("invokeAnimationRequestButton")
        self.invoke_animation_request_button.clicked.connect(
            lambda: self.invoke_current_demo_request(request_kind="animation_preview")
        )

        button_row = QHBoxLayout()
        button_row.addWidget(self.export_action_request_button)
        button_row.addWidget(self.export_animation_request_button)
        button_row.addWidget(self.dry_run_action_request_button)
        button_row.addWidget(self.dry_run_animation_request_button)
        button_row.addWidget(self.invoke_action_request_button)
        button_row.addWidget(self.invoke_animation_request_button)

        self.demo_request_control_summary = QLabel("No demo request control operation yet")
        self.demo_request_control_summary.setObjectName("demoRequestControlSummaryLabel")
        self.demo_request_control_summary.setProperty("role", "muted")
        self.demo_request_control_summary.setWordWrap(True)

        self.demo_request_text = QPlainTextEdit()
        self.demo_request_text.setObjectName("demoRequestText")
        self.demo_request_text.setReadOnly(True)

        self.demo_request_control_text = QPlainTextEdit()
        self.demo_request_control_text.setObjectName("demoRequestControlText")
        self.demo_request_control_text.setReadOnly(True)

        request_splitter = QSplitter(Qt.Vertical)
        request_splitter.addWidget(self.demo_request_text)
        request_splitter.addWidget(self.demo_request_control_text)
        request_splitter.setStretchFactor(0, 2)
        request_splitter.setStretchFactor(1, 1)

        request_root = QWidget()
        request_layout = QVBoxLayout(request_root)
        request_layout.addWidget(self.demo_request_summary)
        request_layout.addWidget(self.demo_request_workspace)
        request_layout.addLayout(button_row)
        request_layout.addWidget(self.demo_request_control_summary)
        request_layout.addWidget(request_splitter)
        self.tabs.addTab(request_root, "Demo Request")

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
            self.demo_request_control = DemoRequestControlState(
                status="pass",
                operation=operation_name,
                request_kind=selection.request_kind,
                dry_run=bool(dry_run),
                workspace_config_path=str(resolved_workspace),
                result_json_path=str(invocation.get("result_json_path") or ""),
                host_key=str(invocation.get("host_key") or ""),
                result_status=str(invocation_result.get("status") or invocation_payload.get("status") or ""),
                invocation_returncode=invocation_meta.get("returncode"),
                payload=invocation,
            )
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
        report = self._selected_report_record()
        if report is None:
            self.details_header.setText("No report selected")
            self.details_text.setPlainText("{}")
            return
        self.details_header.setText(
            f"{report.gate_id or report.name} | {report.status.upper()} | {report.generated_at_utc or 'unknown time'}"
        )
        self.details_text.setPlainText(report_payload_to_text(report))

    def _render_preview_images(self) -> None:
        self.preview_list.clear()
        self.preview_records_by_key.clear()
        for record in self.app_state.preview_images:
            item = QListWidgetItem(f"{record.section} | {record.title}")
            item.setData(Qt.UserRole, record.key)
            self.preview_list.addItem(item)
            self.preview_records_by_key[record.key] = record
        if self.view_state.selected_image_key:
            for index in range(self.preview_list.count()):
                item = self.preview_list.item(index)
                if item.data(Qt.UserRole) == self.view_state.selected_image_key:
                    self.preview_list.setCurrentItem(item)
                    break
        if self.preview_list.currentItem() is None and self.preview_list.count():
            self.preview_list.setCurrentRow(0)
        self._render_preview_image()

    def _render_preview_image(self) -> None:
        preview = self._selected_preview_record()
        if not preview:
            self.preview_label.setText("No preview image selected")
            self.preview_label.setPixmap(QPixmap())
            return
        pixmap = QPixmap(preview.image_path)
        if pixmap.isNull():
            self.preview_label.setText(f"Preview not available:\n{preview.image_path}")
            self.preview_label.setPixmap(QPixmap())
            return
        scaled = pixmap.scaled(
            max(self.preview_label.width(), 640),
            max(self.preview_label.height(), 360),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")

    def _render_metrics(self) -> None:
        rows = list(self.app_state.r3_metrics)
        self.metrics_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("package_id") or "",
                row.get("shot_id") or "",
                row.get("status") or "",
                f"{float(row.get('crop_histogram_l1') or 0.0):.6f}",
                f"{float(row.get('crop_mean_abs_pixel_delta') or 0.0):.6f}",
                f"{float(row.get('full_histogram_l1') or 0.0):.6f}",
                f"{float(row.get('full_mean_abs_pixel_delta') or 0.0):.6f}",
            ]
            for column_index, value in enumerate(values):
                self.metrics_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))

    def _render_slot_table(self) -> None:
        packages = list(self.app_state.slot_debugger.get("packages") or [])
        rows: list[list[str]] = []
        for package in packages:
            package_id = str(package.get("package_id") or "")
            for slot in list(package.get("slots") or []):
                attach_state = dict(slot.get("attach_state") or {})
                component = dict(slot.get("managed_component") or {})
                binding = dict(slot.get("binding") or {})
                coverages = ", ".join(
                    f"{item.get('shot_id')}:{float(item.get('coverage_ratio') or 0.0):.4f}"
                    for item in list(slot.get("tracked_coverages") or [])
                )
                rows.append(
                    [
                        package_id,
                        str(slot.get("slot_name") or ""),
                        str(binding.get("item_kind") or ""),
                        str(component.get("component_name") or ""),
                        str(
                            attach_state.get("resolved_attach_socket_name")
                            or attach_state.get("requested_attach_socket_name")
                            or ""
                        ),
                        coverages,
                        str(len(list(slot.get("slot_conflicts") or []))),
                        str(len(list(slot.get("superseded_bindings") or []))),
                    ]
                )
        self.slot_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                self.slot_table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _render_demo_session(self) -> None:
        session = self.app_state.demo_session
        self.demo_session_package_list.clear()
        self.demo_action_preset_list.clear()
        self.demo_animation_preset_list.clear()

        if session.status != "pass":
            session_path = session.session_manifest_path or "(auto-discovery found no session yet)"
            self.demo_session_summary.setText(f"E2 session status: {session.status.upper()} | {session_path}")
            self.demo_package_details.setPlainText("{}")
            return

        self.demo_session_summary.setText(
            " | ".join(
                [
                    f"Session {session.session_id or 'unknown'}",
                    f"Type {session.session_type or 'unknown'}",
                    f"Packages {len(session.packages)}",
                    f"Host {session.host_key or 'unknown'}",
                    f"Mode {session.mode or 'unknown'}",
                ]
            )
        )
        for record in session.packages:
            item = QListWidgetItem(record.package_id)
            item.setData(Qt.UserRole, record.package_id)
            self.demo_session_package_list.addItem(item)

        selected_package_id = self.view_state.selected_package_id or session.default_package_id
        if selected_package_id:
            for index in range(self.demo_session_package_list.count()):
                item = self.demo_session_package_list.item(index)
                if item.data(Qt.UserRole) == selected_package_id:
                    self.demo_session_package_list.setCurrentItem(item)
                    break
        if self.demo_session_package_list.currentItem() is None and self.demo_session_package_list.count():
            self.demo_session_package_list.setCurrentRow(0)
        self._render_demo_session_package_details()

    def _selected_demo_package_record(self) -> DemoPackageRecord | None:
        return self.app_state.demo_session.package_by_id(self.view_state.selected_package_id)

    def _render_demo_session_package_details(self) -> None:
        package = self._selected_demo_package_record()
        if package is None:
            self.demo_package_details.setPlainText("{}")
            return
        self._render_demo_preset_lists(package)
        self.demo_package_details.setPlainText(json.dumps(package.payload or {}, ensure_ascii=False, indent=2))
        self._render_demo_request()

    def _render_demo_preset_lists(self, package: DemoPackageRecord) -> None:
        self.demo_action_preset_list.clear()
        for preset in package.action_presets:
            item = QListWidgetItem(self._demo_preset_label(preset))
            item.setData(Qt.UserRole, preset.preset_id)
            self.demo_action_preset_list.addItem(item)
        selected_action_preset_id = self.view_state.selected_action_preset_id
        if selected_action_preset_id:
            for index in range(self.demo_action_preset_list.count()):
                item = self.demo_action_preset_list.item(index)
                if item.data(Qt.UserRole) == selected_action_preset_id:
                    self.demo_action_preset_list.setCurrentItem(item)
                    break
        if self.demo_action_preset_list.currentItem() is None and self.demo_action_preset_list.count():
            self.demo_action_preset_list.setCurrentRow(0)

        self.demo_animation_preset_list.clear()
        for preset in package.animation_presets:
            item = QListWidgetItem(self._demo_preset_label(preset))
            item.setData(Qt.UserRole, preset.preset_id)
            self.demo_animation_preset_list.addItem(item)
        selected_animation_preset_id = self.view_state.selected_animation_preset_id
        if selected_animation_preset_id:
            for index in range(self.demo_animation_preset_list.count()):
                item = self.demo_animation_preset_list.item(index)
                if item.data(Qt.UserRole) == selected_animation_preset_id:
                    self.demo_animation_preset_list.setCurrentItem(item)
                    break
        if self.demo_animation_preset_list.currentItem() is None and self.demo_animation_preset_list.count():
            self.demo_animation_preset_list.setCurrentRow(0)

    @staticmethod
    def _demo_preset_label(preset: DemoPresetRecord) -> str:
        parts = [preset.preset_id or "preset", preset.preset_kind]
        if preset.family:
            parts.append(preset.family)
        if preset.status:
            parts.append(preset.status)
        return " | ".join(parts)

    def _render_demo_request(self) -> None:
        payload = self.current_dump_payload()
        demo_request = dict(payload.get("demo_request") or {})
        control_state = dict(payload.get("demo_request_control") or {})
        summary_parts = [
            f"Status {str(demo_request.get('status') or 'unknown').upper()}",
            f"Package {str(demo_request.get('selected_package_id') or 'none')}",
        ]
        request_kinds = list(demo_request.get("request_kinds") or [])
        if request_kinds:
            summary_parts.append(f"Kinds {', '.join(request_kinds)}")
        self.demo_request_summary.setText(" | ".join(summary_parts))
        workspace_path = str(self.current_workspace_config_path or "")
        self.demo_request_workspace.setText(
            f"Workspace config: {workspace_path if workspace_path else 'not configured'}"
        )
        self.demo_request_text.setPlainText(json.dumps(demo_request, ensure_ascii=False, indent=2))
        control_parts = [
            f"Control {str(control_state.get('status') or 'idle').upper()}",
            f"Op {str(control_state.get('operation') or 'none')}",
        ]
        if control_state.get("request_kind"):
            control_parts.append(f"Kind {control_state['request_kind']}")
        if control_state.get("result_status"):
            control_parts.append(f"Result {control_state['result_status']}")
        if control_state.get("result_json_path"):
            control_parts.append(f"Result {control_state['result_json_path']}")
        elif control_state.get("request_json_path"):
            control_parts.append(f"Request {control_state['request_json_path']}")
        self.demo_request_control_summary.setText(" | ".join(control_parts))
        self.demo_request_control_text.setPlainText(json.dumps(control_state, ensure_ascii=False, indent=2))

        request_kind_set = set(request_kinds)
        self.export_action_request_button.setEnabled("action_preview" in request_kind_set)
        self.export_animation_request_button.setEnabled("animation_preview" in request_kind_set)
        workspace_ready = bool(self.current_workspace_config_path and Path(self.current_workspace_config_path).exists())
        self.dry_run_action_request_button.setEnabled("action_preview" in request_kind_set and workspace_ready)
        self.dry_run_animation_request_button.setEnabled("animation_preview" in request_kind_set and workspace_ready)
        self.invoke_action_request_button.setEnabled("action_preview" in request_kind_set and workspace_ready)
        self.invoke_animation_request_button.setEnabled("animation_preview" in request_kind_set and workspace_ready)

    def _selected_report_record(self) -> ReportRecord | None:
        gate_id = self.view_state.selected_report_gate_id
        if not gate_id:
            return None
        return self.app_state.reports_by_gate_id.get(gate_id)

    def _selected_preview_record(self) -> PreviewImageRecord | None:
        image_key = self.view_state.selected_image_key
        if not image_key:
            return None
        return self.preview_records_by_key.get(image_key)

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
