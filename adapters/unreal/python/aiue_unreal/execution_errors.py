from __future__ import annotations


class ActionResultError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        result: dict | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.result = dict(result or {})
        self.warnings = list(warnings or [])
        self.errors = list(errors or [])

