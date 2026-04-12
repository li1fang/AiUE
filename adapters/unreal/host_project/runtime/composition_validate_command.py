from __future__ import annotations

from .common import *


def validate_package(request: dict) -> dict:
    manifest_path = Path(request["manifest"]).expanduser().resolve()
    import_report_path = Path(request.get("import_report") or manifest_path.parent / "ue_import_report.local.json").expanduser().resolve()
    validation_report_path = Path(request.get("validation_report") or manifest_path.parent / "ue_validation_report.local.json").expanduser().resolve()
    warnings: list[str] = []
    errors: list[str] = []

    if not manifest_path.exists():
        return {
            "status": "fail",
            "manifest_path": str(manifest_path),
            "import_report_path": str(import_report_path),
            "validation_report_path": str(validation_report_path),
            "warnings": [],
            "errors": [f"manifest_missing:{manifest_path}"],
        }

    manifest = read_json(manifest_path)
    import_report = read_json(import_report_path) if import_report_path.exists() else None
    validation_report = read_json(validation_report_path) if validation_report_path.exists() else None

    if not import_report:
        errors.append(f"import_report_missing:{import_report_path}")
    if not validation_report:
        errors.append(f"validation_report_missing:{validation_report_path}")

    validation_status = ""
    checks: dict = {}
    if validation_report:
        validation_status = str(validation_report.get("status") or "")
        checks = dict(validation_report.get("checks") or {})
        validation_failures = list(validation_report.get("failures") or [])
        validation_warnings = list(validation_report.get("warnings") or [])
        warnings.extend(validation_warnings)
        if validation_status.lower() != "pass":
            errors.extend(validation_failures or [f"validation_status:{validation_status or 'unknown'}"])

    if import_report:
        warnings.extend(list(import_report.get("warnings") or []))

    return {
        "status": "pass" if not errors else "fail",
        "generated_at_utc": now_utc(),
        "manifest_path": str(manifest_path),
        "manifest_exists": True,
        "sample_id": manifest.get("sample_id"),
        "package_id": manifest.get("package_id"),
        "source_file": manifest.get("source_file"),
        "output_fbx": manifest.get("output_fbx"),
        "import_report_path": str(import_report_path),
        "import_report_exists": bool(import_report),
        "validation_report_path": str(validation_report_path),
        "validation_report_exists": bool(validation_report),
        "validation_status": validation_status,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }


__all__ = ["validate_package"]
