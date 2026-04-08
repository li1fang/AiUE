from __future__ import annotations

SUPPORTED_MODES = ("cmd_nullrhi", "cmd_rendered", "editor_rendered", "dual", "all")
EXECUTION_MODES = ("cmd_nullrhi", "cmd_rendered", "editor_rendered")


def normalize_mode(mode: str | None) -> str:
    value = (mode or "cmd_nullrhi").strip()
    if value not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported AiUE mode: {value}")
    return value


def expand_modes(mode: str | None) -> list[str]:
    value = normalize_mode(mode)
    if value == "dual":
        return ["cmd_nullrhi", "editor_rendered"]
    if value == "all":
        return list(EXECUTION_MODES)
    return [value]
