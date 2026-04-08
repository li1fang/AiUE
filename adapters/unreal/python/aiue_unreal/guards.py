from __future__ import annotations


class GuardError(RuntimeError):
    pass


DESTRUCTIVE_COMMANDS = {
    "delete-generated-assets",
    "delete-suite-registry",
    "rebuild-package",
}


def ensure_action_allowed(action_spec: dict, metadata: dict):
    if metadata.get("destructive") and not action_spec.get("allow_destructive"):
        raise GuardError(
            f"Command '{action_spec.get('command')}' is destructive. "
            "Re-run with allow_destructive=true."
        )
