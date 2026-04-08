from __future__ import annotations

import hashlib
import json
from pathlib import Path


def load_json(path) -> dict:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path, payload: dict) -> Path:
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path


def hash_file(path) -> str:
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand_workspace_value(value, project_root: Path, config_dir: Path):
    if value is None:
        return None
    text = str(value)
    if not text:
        return text
    if text.startswith("/Game/"):
        return text
    expanded = text.replace("${project_root}", str(project_root))
    expanded = expanded.replace("${config_dir}", str(config_dir))
    expanded = expanded.replace("${workspace_dir}", str(config_dir))
    expanded = Path(expanded).expanduser()
    if expanded.is_absolute():
        return str(expanded.resolve())
    return str((config_dir / expanded).resolve())


def load_workspace_config(config_path) -> dict:
    resolved_path = Path(config_path).expanduser().resolve()
    raw = load_json(resolved_path)
    config_dir = resolved_path.parent
    project_root = config_dir.parent
    workspace_version = raw.get("version") or raw.get("schema_version") or "0.1.0"
    resolved_paths = {
        key: expand_workspace_value(value, project_root, config_dir)
        for key, value in (raw.get("paths") or {}).items()
    }
    sections = {}
    for section_name in ("defaults", "visual_review", "portability", "open_source", "animation", "probe"):
        values = {}
        for key, value in (raw.get(section_name) or {}).items():
            if key.endswith("_root") or key.endswith("_path"):
                values[key] = expand_workspace_value(value, project_root, config_dir)
            else:
                values[key] = value
        sections[section_name] = values
    return {
        "schema_version": raw.get("schema_version", 1),
        "version": workspace_version,
        "project_root": str(project_root.resolve()),
        "config_path": str(resolved_path),
        "config_hash": hash_file(resolved_path),
        "paths": resolved_paths,
        **sections,
        "raw": raw,
    }
