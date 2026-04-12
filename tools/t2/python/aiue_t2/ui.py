from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from aiue_t2.state import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    AppState,
    DemoRequestRecord,
    DemoSessionRecord,
    GovernanceBalanceRecord,
    Pv1SignoffRecord,
    TestGovernanceRecord,
    ViewState,
    build_default_view_state,
    load_workbench_state,
)
from aiue_t2.demo_control_state import load_demo_control_state, write_demo_control_run
from aiue_t2.demo_review_compare_state import (
    build_demo_review_compare_focus,
    load_demo_review_compare_state,
)
from aiue_t2.demo_review_history_state import build_demo_review_history_focus, load_demo_review_history_state
from aiue_t2.demo_review_state import build_demo_review_focus, build_demo_review_state
from aiue_t2.demo_review_replay_state import load_demo_review_replay_state
from aiue_t2.demo_round_state import load_demo_round_state
from aiue_t2.demo_request_runner import export_demo_request, invoke_demo_request, load_demo_request_selection
from aiue_t2.ui_demo import DemoRequestControlState, DemoRequestPanel, DemoReviewPanel, DemoSessionPanel
from aiue_t2.ui_sections import (
    ContrastComparePanel,
    ContrastTriptychPanel,
    DetailsPanel,
    ImagesPanel,
    SlotDebuggerPanel,
    SummaryCard,
)
from aiue_t2.workbench_demo_ops import WorkbenchDemoOpsMixin
from aiue_t2.workbench_render import WorkbenchRenderMixin


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

class WorkbenchWindow(WorkbenchRenderMixin, WorkbenchDemoOpsMixin, QMainWindow):
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
        selected_review_compare_index: int = 0,
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
        self.requested_selected_review_compare_index = max(0, int(selected_review_compare_index or 0))
        self._export_demo_request_fn = export_demo_request
        self._invoke_demo_request_fn = invoke_demo_request
        self._load_demo_request_selection_fn = load_demo_request_selection
        self._write_demo_control_run_fn = write_demo_control_run
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
            quality_summaries={
                "diversity_matrix": {"status": "missing", "coverage_axes": []},
                "m1_material_proof": {"status": "missing", "packages": []},
                "q5c_lite": {"status": "missing", "packages": [], "diagnostic_class_counts": {}},
                "q5c_contrast": {"status": "missing", "packages": []},
            },
            slot_debugger={"package_count": 0, "packages": []},
            governance_balance=GovernanceBalanceRecord(status="missing"),
            test_governance=TestGovernanceRecord(status="missing"),
            pv1_signoff=Pv1SignoffRecord(status="missing"),
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
        self.demo_review_history_state: dict = {"status": "missing", "recent_events": [], "package_history_counts": {}}
        self.demo_review_history_focus: dict = {"status": "missing", "selected_package_id": "", "event_count": 0}
        self.demo_review_compare_state: dict = {"status": "missing", "package_compares": [], "counts": {}}
        self.demo_review_compare_focus: dict = {"status": "missing", "selected_package_id": "", "compare_ready": False}
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

        self.test_governance_summary = QLabel("")
        self.test_governance_summary.setObjectName("testGovernanceSummary")
        self.test_governance_summary.setWordWrap(True)
        self.test_governance_summary.setProperty("role", "muted")
        self.test_governance_summary.setStyleSheet("padding: 0 2px 6px 2px;")
        self.test_governance_summary.setVisible(False)
        root_layout.addWidget(self.test_governance_summary)

        self.pv1_signoff_summary = QLabel("")
        self.pv1_signoff_summary.setObjectName("pv1SignoffSummary")
        self.pv1_signoff_summary.setWordWrap(True)
        self.pv1_signoff_summary.setProperty("role", "muted")
        self.pv1_signoff_summary.setStyleSheet("padding: 0 2px 6px 2px;")
        self.pv1_signoff_summary.setVisible(False)
        root_layout.addWidget(self.pv1_signoff_summary)

        self.material_proof_summary = QLabel("")
        self.material_proof_summary.setObjectName("materialProofSummary")
        self.material_proof_summary.setWordWrap(True)
        self.material_proof_summary.setProperty("role", "muted")
        self.material_proof_summary.setStyleSheet("padding: 0 2px 6px 2px;")
        self.material_proof_summary.setVisible(False)
        root_layout.addWidget(self.material_proof_summary)

        self.diversity_matrix_summary = QLabel("")
        self.diversity_matrix_summary.setObjectName("diversityMatrixSummary")
        self.diversity_matrix_summary.setWordWrap(True)
        self.diversity_matrix_summary.setProperty("role", "muted")
        self.diversity_matrix_summary.setStyleSheet("padding: 0 2px 6px 2px;")
        self.diversity_matrix_summary.setVisible(False)
        root_layout.addWidget(self.diversity_matrix_summary)

        self.q5c_quality_summary = QLabel("")
        self.q5c_quality_summary.setObjectName("q5cQualitySummary")
        self.q5c_quality_summary.setWordWrap(True)
        self.q5c_quality_summary.setProperty("role", "muted")
        self.q5c_quality_summary.setStyleSheet("padding: 6px 2px 10px 2px;")
        self.q5c_quality_summary.setVisible(False)
        root_layout.addWidget(self.q5c_quality_summary)

        self.q5c_contrast_summary = QLabel("")
        self.q5c_contrast_summary.setObjectName("q5cContrastSummary")
        self.q5c_contrast_summary.setWordWrap(True)
        self.q5c_contrast_summary.setProperty("role", "muted")
        self.q5c_contrast_summary.setStyleSheet("padding: 0 2px 6px 2px;")
        self.q5c_contrast_summary.setVisible(False)
        root_layout.addWidget(self.q5c_contrast_summary)

        self.q5c_contrast_case_list = QListWidget()
        self.q5c_contrast_case_list.setObjectName("q5cContrastCaseList")
        self.q5c_contrast_case_list.setMaximumHeight(120)
        self.q5c_contrast_case_list.currentItemChanged.connect(self._on_q5c_contrast_case_changed)
        self.q5c_contrast_case_list.setVisible(False)
        root_layout.addWidget(self.q5c_contrast_case_list)

        self.q5c_contrast_triptych = ContrastTriptychPanel()
        self.q5c_contrast_triptych.setObjectName("q5cContrastTriptych")
        self.q5c_contrast_triptych.setVisible(False)
        root_layout.addWidget(self.q5c_contrast_triptych)

        self.q5c_contrast_compare_panel = ContrastComparePanel()
        self.q5c_contrast_compare_panel.setObjectName("q5cContrastComparePanel")
        self.q5c_contrast_compare_panel.setVisible(False)
        root_layout.addWidget(self.q5c_contrast_compare_panel)

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
        self.open_compare_action_after_button = self.demo_review_panel.open_compare_action_after_button
        self.open_compare_animation_after_button = self.demo_review_panel.open_compare_animation_after_button
        self.newer_compare_button = self.demo_review_panel.newer_compare_button
        self.older_compare_button = self.demo_review_panel.older_compare_button
        self.replay_action_button = self.demo_review_panel.replay_action_button
        self.replay_animation_button = self.demo_review_panel.replay_animation_button
        self.demo_review_replay_summary = self.demo_review_panel.demo_review_replay_summary
        self.demo_review_history_summary = self.demo_review_panel.demo_review_history_summary
        self.demo_review_compare_summary = self.demo_review_panel.demo_review_compare_summary
        self.demo_review_panel.bind_callbacks(
            open_review_artifact=lambda: self.open_demo_review_artifact(),
            open_hero_before=lambda: self.open_demo_review_hero_before(),
            open_action_after=lambda: self.open_demo_review_action_after(),
            open_animation_after=lambda: self.open_demo_review_animation_after(),
            open_compare_action_after=lambda: self.open_demo_review_compare_action_after(),
            open_compare_animation_after=lambda: self.open_demo_review_compare_animation_after(),
            newer_compare=lambda: self.step_demo_review_compare(-1),
            older_compare=lambda: self.step_demo_review_compare(1),
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
        self.demo_review_history_state = load_demo_review_history_state(
            self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path
        )
        self.demo_review_history_focus = build_demo_review_history_focus(
            self.demo_review_history_state,
            selected_package_id=self.view_state.selected_package_id,
        )
        self.demo_review_compare_state = load_demo_review_compare_state(
            self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path,
            demo_review_history_state=self.demo_review_history_state,
        )
        self.demo_review_compare_focus = build_demo_review_compare_focus(
            self.demo_review_compare_state,
            selected_package_id=self.view_state.selected_package_id,
            selected_pair_index=self.view_state.selected_review_compare_index,
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
        self.view_state.selected_review_compare_index = max(0, int(self.requested_selected_review_compare_index or 0))

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
        payload["demo_review_history_state"] = dict(self.demo_review_history_state)
        payload["demo_review_history_focus"] = dict(self.demo_review_history_focus)
        payload["demo_review_compare_state"] = dict(self.demo_review_compare_state)
        payload["demo_review_compare_focus"] = dict(self.demo_review_compare_focus)
        payload["demo_review_replay_control"] = dict(self.demo_review_replay_control)
        payload["demo_round_control"] = dict(self.demo_round_control)
        payload["demo_request_control"] = self.demo_request_control.to_dump_dict()
        return payload

    def current_error_codes(self) -> list[str]:
        return [error.code for error in self.app_state.errors]
