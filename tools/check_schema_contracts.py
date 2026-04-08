from __future__ import annotations

import argparse
import json
from pathlib import Path


ENVELOPE_FIELDS = ["schema_version", "tool_name", "workflow_pack", "generated_at_utc", "compatibility"]

SCHEMA_RULES = {
    "schemas/aiue_action_spec.schema.json": {
        "required_properties": ENVELOPE_FIELDS + ["command", "mode", "params", "allow_destructive", "dry_run", "output_path"],
        "required_keys": ["$schema", "title", "type", "properties"],
    },
    "schemas/aiue_action_result.schema.json": {
        "required_properties": ENVELOPE_FIELDS + ["run_id", "command", "mode", "status", "success", "warnings", "errors", "result"],
        "required_keys": ["$schema", "title", "type", "properties", "required"],
    },
    "schemas/aiue_capabilities.schema.json": {
        "required_properties": ENVELOPE_FIELDS + ["run_id", "preferred_capture_mode", "recommended_capture_mode", "capture_policy", "capabilities"],
        "required_keys": ["$schema", "title", "type", "properties"],
    },
    "schemas/aiue_probe_report.schema.json": {
        "required_properties": ENVELOPE_FIELDS + ["run_id", "workspace_config_path", "mode", "capabilities_path", "probe_report_path", "api_matrix_path"],
        "required_keys": ["$schema", "title", "type", "properties", "required"],
    },
    "schemas/aiue_capture_lab_report.schema.json": {
        "required_properties": ENVELOPE_FIELDS + ["run_id", "suite_name", "run_root", "matrix_csv_path", "recommended_capture_policy_path", "counts"],
        "required_keys": ["$schema", "title", "type", "properties"],
    },
    "schemas/aiue_capture_policy.schema.json": {
        "required_properties": ENVELOPE_FIELDS + ["recommended_mode", "recommended_completion_strategy", "confidence", "derived_from", "policy_reasoning"],
        "required_keys": ["$schema", "title", "type", "properties"],
    },
}


def validate_schema(repo_root: Path, relative_path: str, rules: dict) -> dict:
    path = repo_root / relative_path
    if not path.exists():
        return {"path": str(path), "status": "fail", "errors": ["missing_schema_file"]}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    errors = []
    for key in rules["required_keys"]:
        if key not in payload:
            errors.append(f"missing_top_level_key:{key}")
    properties = payload.get("properties") or {}
    for prop in rules["required_properties"]:
        if prop not in properties:
            errors.append(f"missing_property:{prop}")
    if payload.get("type") != "object":
        errors.append("schema_type_must_be_object")
    return {
        "path": str(path),
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Check AiUE schema contracts.")
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    results = [validate_schema(repo_root, relative_path, rules) for relative_path, rules in SCHEMA_RULES.items()]
    failed = [item for item in results if item["status"] != "pass"]
    report = {
        "status": "pass" if not failed else "fail",
        "checked_schemas": len(results),
        "failed_schemas": len(failed),
        "results": results,
    }
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
