from __future__ import annotations

import json
from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from aiue_t2.state import DemoPackageRecord, DemoPresetRecord, DemoSessionRecord


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


class DemoSessionPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.demo_session_summary = QLabel("No E2 session loaded")
        self.demo_session_summary.setObjectName("demoSessionSummaryLabel")
        self.demo_session_summary.setProperty("role", "muted")
        self.demo_session_summary.setWordWrap(True)

        self.demo_session_package_list = QListWidget()
        self.demo_session_package_list.setObjectName("demoSessionPackageList")

        self.demo_action_preset_list = QListWidget()
        self.demo_action_preset_list.setObjectName("demoActionPresetList")

        self.demo_animation_preset_list = QListWidget()
        self.demo_animation_preset_list.setObjectName("demoAnimationPresetList")

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

        layout = QVBoxLayout(self)
        layout.addWidget(session_splitter)

    def render_session(self, session: DemoSessionRecord, selected_package_id: str | None) -> None:
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

        resolved_package_id = selected_package_id or session.default_package_id
        if resolved_package_id:
            for index in range(self.demo_session_package_list.count()):
                item = self.demo_session_package_list.item(index)
                if item.data(Qt.UserRole) == resolved_package_id:
                    self.demo_session_package_list.setCurrentItem(item)
                    break
        if self.demo_session_package_list.currentItem() is None and self.demo_session_package_list.count():
            self.demo_session_package_list.setCurrentRow(0)

    def render_package_details(
        self,
        package: DemoPackageRecord | None,
        *,
        selected_action_preset_id: str | None,
        selected_animation_preset_id: str | None,
    ) -> None:
        if package is None:
            self.demo_action_preset_list.clear()
            self.demo_animation_preset_list.clear()
            self.demo_package_details.setPlainText("{}")
            return
        self._render_preset_list(
            self.demo_action_preset_list,
            package.action_presets,
            selected_action_preset_id,
        )
        self._render_preset_list(
            self.demo_animation_preset_list,
            package.animation_presets,
            selected_animation_preset_id,
        )
        self.demo_package_details.setPlainText(json.dumps(package.payload or {}, ensure_ascii=False, indent=2))

    def _render_preset_list(
        self,
        list_widget: QListWidget,
        presets: list[DemoPresetRecord],
        selected_preset_id: str | None,
    ) -> None:
        list_widget.clear()
        for preset in presets:
            item = QListWidgetItem(self._demo_preset_label(preset))
            item.setData(Qt.UserRole, preset.preset_id)
            list_widget.addItem(item)
        if selected_preset_id:
            for index in range(list_widget.count()):
                item = list_widget.item(index)
                if item.data(Qt.UserRole) == selected_preset_id:
                    list_widget.setCurrentItem(item)
                    break
        if list_widget.currentItem() is None and list_widget.count():
            list_widget.setCurrentRow(0)

    @staticmethod
    def _demo_preset_label(preset: DemoPresetRecord) -> str:
        parts = [preset.preset_id or "preset", preset.preset_kind]
        if preset.family:
            parts.append(preset.family)
        if preset.status:
            parts.append(preset.status)
        return " | ".join(parts)


class DemoRequestPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
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

        self.export_animation_request_button = QPushButton("Export Animation Request")
        self.export_animation_request_button.setObjectName("exportAnimationRequestButton")

        self.dry_run_action_request_button = QPushButton("Dry Run Action Request")
        self.dry_run_action_request_button.setObjectName("dryRunActionRequestButton")

        self.dry_run_animation_request_button = QPushButton("Dry Run Animation Request")
        self.dry_run_animation_request_button.setObjectName("dryRunAnimationRequestButton")

        self.invoke_action_request_button = QPushButton("Invoke Action Request")
        self.invoke_action_request_button.setObjectName("invokeActionRequestButton")

        self.invoke_animation_request_button = QPushButton("Invoke Animation Request")
        self.invoke_animation_request_button.setObjectName("invokeAnimationRequestButton")

        self.invoke_session_round_button = QPushButton("Invoke Session Round")
        self.invoke_session_round_button.setObjectName("invokeSessionRoundButton")

        button_row = QHBoxLayout()
        button_row.addWidget(self.export_action_request_button)
        button_row.addWidget(self.export_animation_request_button)
        button_row.addWidget(self.dry_run_action_request_button)
        button_row.addWidget(self.dry_run_animation_request_button)
        button_row.addWidget(self.invoke_action_request_button)
        button_row.addWidget(self.invoke_animation_request_button)
        button_row.addWidget(self.invoke_session_round_button)

        self.demo_request_control_summary = QLabel("No demo request control operation yet")
        self.demo_request_control_summary.setObjectName("demoRequestControlSummaryLabel")
        self.demo_request_control_summary.setProperty("role", "muted")
        self.demo_request_control_summary.setWordWrap(True)

        self.demo_control_state_summary = QLabel("No controlled demo runs yet")
        self.demo_control_state_summary.setObjectName("demoControlStateSummaryLabel")
        self.demo_control_state_summary.setProperty("role", "muted")
        self.demo_control_state_summary.setWordWrap(True)

        self.demo_request_text = QPlainTextEdit()
        self.demo_request_text.setObjectName("demoRequestText")
        self.demo_request_text.setReadOnly(True)

        self.demo_request_control_text = QPlainTextEdit()
        self.demo_request_control_text.setObjectName("demoRequestControlText")
        self.demo_request_control_text.setReadOnly(True)

        self.demo_control_state_text = QPlainTextEdit()
        self.demo_control_state_text.setObjectName("demoControlStateText")
        self.demo_control_state_text.setReadOnly(True)

        request_splitter = QSplitter(Qt.Vertical)
        request_splitter.addWidget(self.demo_request_text)
        request_splitter.addWidget(self.demo_request_control_text)
        request_splitter.addWidget(self.demo_control_state_text)
        request_splitter.setStretchFactor(0, 2)
        request_splitter.setStretchFactor(1, 1)
        request_splitter.setStretchFactor(2, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.demo_request_summary)
        layout.addWidget(self.demo_request_workspace)
        layout.addLayout(button_row)
        layout.addWidget(self.demo_request_control_summary)
        layout.addWidget(self.demo_control_state_summary)
        layout.addWidget(request_splitter)

    def bind_callbacks(
        self,
        *,
        export_action,
        export_animation,
        dry_run_action,
        dry_run_animation,
        invoke_action,
        invoke_animation,
        invoke_session_round,
    ) -> None:
        self.export_action_request_button.clicked.connect(export_action)
        self.export_animation_request_button.clicked.connect(export_animation)
        self.dry_run_action_request_button.clicked.connect(dry_run_action)
        self.dry_run_animation_request_button.clicked.connect(dry_run_animation)
        self.invoke_action_request_button.clicked.connect(invoke_action)
        self.invoke_animation_request_button.clicked.connect(invoke_animation)
        self.invoke_session_round_button.clicked.connect(invoke_session_round)

    def render_request(
        self,
        demo_request: dict,
        control_state: dict,
        demo_control_state: dict,
        demo_round_control: dict,
        demo_round_state: dict,
        *,
        workspace_path: str,
    ) -> None:
        summary_parts = [
            f"Status {str(demo_request.get('status') or 'unknown').upper()}",
            f"Package {str(demo_request.get('selected_package_id') or 'none')}",
        ]
        request_kinds = list(demo_request.get("request_kinds") or [])
        if request_kinds:
            summary_parts.append(f"Kinds {', '.join(request_kinds)}")
        self.demo_request_summary.setText(" | ".join(summary_parts))
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

        selected_package_id = str(demo_request.get("selected_package_id") or "")
        last_runs_by_package = dict(demo_control_state.get("last_runs_by_package") or {})
        current_package_runs = dict(last_runs_by_package.get(selected_package_id) or {})
        state_parts = [
            f"Last Controlled Runs {str(demo_control_state.get('status') or 'missing').upper()}",
            f"Package {selected_package_id or 'none'}",
            f"Run Kinds {', '.join(sorted(current_package_runs)) if current_package_runs else 'none'}",
        ]
        if demo_round_control:
            state_parts.append(f"Round {str(demo_round_control.get('status') or 'idle').upper()}")
        self.demo_control_state_summary.setText(" | ".join(state_parts))
        self.demo_control_state_text.setPlainText(
            json.dumps(
                {
                    "status": demo_control_state.get("status"),
                    "selected_package_id": demo_control_state.get("selected_package_id"),
                    "selected_action_preset_id": demo_control_state.get("selected_action_preset_id"),
                    "selected_animation_preset_id": demo_control_state.get("selected_animation_preset_id"),
                    "package_run_counts": demo_control_state.get("package_run_counts"),
                    "last_runs_for_selected_package": current_package_runs,
                    "control_state_path": demo_control_state.get("control_state_path"),
                    "round_control": demo_round_control,
                    "round_state": demo_round_state,
                    "errors": demo_control_state.get("errors"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        request_kind_set = set(request_kinds)
        workspace_ready = bool(workspace_path)
        self.export_action_request_button.setEnabled("action_preview" in request_kind_set)
        self.export_animation_request_button.setEnabled("animation_preview" in request_kind_set)
        self.dry_run_action_request_button.setEnabled("action_preview" in request_kind_set and workspace_ready)
        self.dry_run_animation_request_button.setEnabled("animation_preview" in request_kind_set and workspace_ready)
        self.invoke_action_request_button.setEnabled("action_preview" in request_kind_set and workspace_ready)
        self.invoke_animation_request_button.setEnabled("animation_preview" in request_kind_set and workspace_ready)
        self.invoke_session_round_button.setEnabled(
            "action_preview" in request_kind_set and "animation_preview" in request_kind_set and workspace_ready
        )
