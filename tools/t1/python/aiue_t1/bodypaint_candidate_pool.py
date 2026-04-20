from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


def normalize_token(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def toy_yard_sample_key(canonical_sample_id: str | None) -> str:
    token = normalize_token(canonical_sample_id)
    if token.startswith("sample_"):
        token = token[len("sample_") :]
    return token


def toy_yard_package_key(canonical_package_id: str | None) -> str:
    token = normalize_token(canonical_package_id)
    if token.startswith("pkg_"):
        token = token[len("pkg_") :]
    return token


def compatible_lookup_keys(token: str | None) -> list[str]:
    normalized = normalize_token(token)
    if not normalized:
        return []
    keys = [normalized]
    parts = normalized.split("_")
    while len(parts) > 3:
        parts = parts[:-1]
        candidate = "_".join(parts)
        if candidate and candidate not in keys:
            keys.append(candidate)
    return keys


@dataclass(frozen=True)
class ToyYardCharacterCandidate:
    package_db_id: int
    sample_db_id: int
    canonical_package_id: str
    canonical_sample_id: str
    display_name: str
    source_game: str
    package_role: str
    warehouse_status: str

    @property
    def sample_key(self) -> str:
        return toy_yard_sample_key(self.canonical_sample_id)

    @property
    def package_key(self) -> str:
        return toy_yard_package_key(self.canonical_package_id)

    @property
    def display_key(self) -> str:
        return normalize_token(self.display_name)


@dataclass(frozen=True)
class LocalConversionEntry:
    manifest_path: Path
    mesh_path: Path
    sample_key: str
    package_key: str
    display_key: str
    score: int


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def query_toy_yard_character_candidates(sqlite_path: Path) -> list[ToyYardCharacterCandidate]:
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT p.id AS package_db_id,
                   s.id AS sample_db_id,
                   p.canonical_package_id,
                   s.canonical_sample_id,
                   s.display_name,
                   s.source_game,
                   p.package_role,
                   p.warehouse_status
            FROM packages p
            JOIN samples s ON s.id = p.sample_id
            WHERE p.consumer_ready = 1
              AND (
                p.content_bucket = 'Characters'
                OR p.package_role IN ('character', 'character_bundle_member', 'standalone_character', 'unknown')
              )
            ORDER BY s.display_name, p.id
            """
        ).fetchall()
    finally:
        conn.close()

    return [
        ToyYardCharacterCandidate(
            package_db_id=int(row["package_db_id"]),
            sample_db_id=int(row["sample_db_id"]),
            canonical_package_id=str(row["canonical_package_id"] or ""),
            canonical_sample_id=str(row["canonical_sample_id"] or ""),
            display_name=str(row["display_name"] or ""),
            source_game=str(row["source_game"] or ""),
            package_role=str(row["package_role"] or ""),
            warehouse_status=str(row["warehouse_status"] or ""),
        )
        for row in rows
    ]


def _entry_score(manifest_path: Path) -> int:
    parts = {part.lower() for part in manifest_path.parts}
    score = 0
    if "_e2e_runs" not in parts:
        score += 1000
    if "core_regression" in parts:
        score += 150
    if "stress" in parts:
        score += 100
    if "smoke" in parts:
        score += 50
    if "weapon" in parts or "剑" in parts:
        score -= 500
    score -= len(manifest_path.parts)
    return score


def _first_mesh_near_manifest(manifest_path: Path) -> Path | None:
    candidates = sorted(path for path in manifest_path.parent.glob("*.fbx") if path.is_file())
    if candidates:
        return candidates[0]
    return None


def collect_local_conversion_entries(conversion_root: Path) -> list[LocalConversionEntry]:
    entries: list[LocalConversionEntry] = []
    for manifest_path in sorted(conversion_root.rglob("manifest.json")):
        mesh_path = _first_mesh_near_manifest(manifest_path)
        if mesh_path is None:
            continue
        try:
            manifest = _load_json(manifest_path)
        except Exception:
            continue
        sample_key = normalize_token(str(manifest.get("sample_id") or ""))
        package_key = normalize_token(str(manifest.get("package_id") or ""))
        display_key = normalize_token(mesh_path.stem)
        entries.append(
            LocalConversionEntry(
                manifest_path=manifest_path.resolve(),
                mesh_path=mesh_path.resolve(),
                sample_key=sample_key,
                package_key=package_key,
                display_key=display_key,
                score=_entry_score(manifest_path),
            )
        )
    return entries


def choose_best_entry(entries: list[LocalConversionEntry]) -> LocalConversionEntry | None:
    if not entries:
        return None
    return sorted(
        entries,
        key=lambda item: (
            -item.score,
            len(item.manifest_path.parts),
            str(item.manifest_path),
        ),
    )[0]


def build_conversion_indexes(entries: list[LocalConversionEntry]) -> dict[str, dict[str, list[LocalConversionEntry]]]:
    by_sample: dict[str, list[LocalConversionEntry]] = {}
    by_package: dict[str, list[LocalConversionEntry]] = {}
    by_display: dict[str, list[LocalConversionEntry]] = {}
    for entry in entries:
        if entry.sample_key:
            by_sample.setdefault(entry.sample_key, []).append(entry)
        if entry.package_key:
            by_package.setdefault(entry.package_key, []).append(entry)
        if entry.display_key:
            by_display.setdefault(entry.display_key, []).append(entry)
    return {
        "sample": by_sample,
        "package": by_package,
        "display": by_display,
    }


def match_candidate_to_entry(
    candidate: ToyYardCharacterCandidate,
    indexes: dict[str, dict[str, list[LocalConversionEntry]]],
) -> tuple[LocalConversionEntry | None, str]:
    for package_key in compatible_lookup_keys(candidate.package_key):
        package_matches = indexes["package"].get(package_key, [])
        if package_matches:
            return choose_best_entry(package_matches), "package_key"
    for sample_key in compatible_lookup_keys(candidate.sample_key):
        sample_matches = indexes["sample"].get(sample_key, [])
        if sample_matches:
            return choose_best_entry(sample_matches), "sample_key"
    display_matches = indexes["display"].get(candidate.display_key, [])
    if display_matches:
        return choose_best_entry(display_matches), "display_key"
    return None, "unmatched"


def ensure_tag_rows(sqlite_path: Path, rows: list[tuple[str, int, str]]) -> int:
    conn = sqlite3.connect(str(sqlite_path))
    try:
        inserted = 0
        for entity_type, entity_id, tag in rows:
            existing = conn.execute(
                "SELECT 1 FROM tags WHERE entity_type = ? AND entity_id = ? AND tag = ? LIMIT 1",
                (entity_type, entity_id, tag),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                "INSERT INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
                (entity_type, entity_id, tag),
            )
            inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()
