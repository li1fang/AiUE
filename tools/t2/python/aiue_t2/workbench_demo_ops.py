from __future__ import annotations

from pathlib import Path

from aiue_t2.demo_review_history_state import write_demo_review_history_event
from aiue_t2.demo_review_replay_state import write_demo_review_replay_run
from aiue_t2.demo_round_state import write_demo_round_state
from aiue_t2.ui_demo import DemoRequestControlState


class WorkbenchDemoOpsMixin:
    def open_demo_session_manifest(self) -> None:
        session_manifest_path = self.app_state.demo_session.session_manifest_path
        if session_manifest_path:
            self._open_in_explorer(session_manifest_path)

    def open_demo_review_artifact(self) -> None:
        target = self.demo_review_focus.get("review_state_path") or self.demo_review_state.get("review_state_path") or ""
        self._open_in_explorer(str(target))

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
            selection = self._load_demo_request_selection_fn(
                **self._selected_demo_request_kwargs(),
                request_kind=request_kind,
            )
            invocation = self._invoke_demo_request_fn(
                selection,
                workspace_config=resolved_workspace,
                dry_run=False,
            )
            invocation_payload = dict(invocation.get("payload") or {})
            invocation_result = dict(invocation_payload.get("result") or {})
            invocation_meta = dict(invocation.get("invocation") or {})
            self.demo_control_state = self._write_demo_control_run_fn(
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
            package_replays = dict(
                (self.demo_review_replay_state.get("last_replays_by_package") or {}).get(str(selection.selected_package_id or ""), {}) or {}
            )
            self.demo_review_history_state = write_demo_review_history_event(
                session_manifest_path=self.app_state.demo_session.session_manifest_path or self.current_session_manifest_path,
                source_review_state_path=str(self.demo_review_state.get("review_state_path") or ""),
                source_replay_state_path=str(self.demo_review_replay_state.get("replay_state_path") or ""),
                session_id=self.app_state.demo_session.session_id,
                selected_package_id=selection.selected_package_id,
                request_kind=selection.request_kind,
                replay_run=dict(package_replays.get(selection.request_kind) or {}),
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
            selection = self._load_demo_request_selection_fn(
                **self._selected_demo_request_kwargs(),
                request_kind=request_kind,
            )
            exported_path = self._export_demo_request_fn(selection)
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
            selection = self._load_demo_request_selection_fn(
                **self._selected_demo_request_kwargs(),
                request_kind=request_kind,
            )
            invocation = self._invoke_demo_request_fn(
                selection,
                workspace_config=resolved_workspace,
                dry_run=dry_run,
            )
            invocation_payload = dict(invocation.get("payload") or {})
            invocation_result = dict(invocation_payload.get("result") or {})
            invocation_meta = dict(invocation.get("invocation") or {})
            self.demo_control_state = self._write_demo_control_run_fn(
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
            errors.append(
                {
                    "id": "round_action_motion_not_verified",
                    "message": "The session round action_preview credibility check did not verify motion.",
                }
            )
        if animation_invoke and not bool(animation_credibility.get("animation_pose_verified")):
            errors.append(
                {
                    "id": "round_animation_pose_not_verified",
                    "message": "The session round animation_preview credibility check did not verify pose change.",
                }
            )
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
                            "errors": [
                                {
                                    "id": "round_presets_missing",
                                    "message": "The package does not have both action and animation presets.",
                                }
                            ],
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
