from __future__ import annotations

import zipfile
from pathlib import Path

from aiue_t1.base_mesh_trial import discover_base_mesh_items, parse_base_mesh_inventory, ue_suitability_signal


def _write_zip(path: Path, entries: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def test_parse_base_mesh_inventory_extracts_archive_rows(tmp_path: Path):
    inventory_path = tmp_path / "inventory.md"
    inventory_path.write_text(
        "\n".join(
            [
                "### BM-001",
                "- source archive: `C:\\sample\\C4D.zip`",
                "- family guess: `3d / base_mesh / body_base`",
                "- trial note: first lane",
                "",
                "### BM-004",
                "- source archive: `C:\\sample\\A010.zip`",
                "- family guess: `3d / anime_style / body_base / multi_variant_pack`",
                "- trial note: second lane",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = parse_base_mesh_inventory(inventory_path)

    assert [row["archive_id"] for row in rows] == ["BM-001", "BM-004"]
    assert rows[0]["source_archive"] == r"C:\sample\C4D.zip"
    assert rows[1]["family_guess"] == "3d / anime_style / body_base / multi_variant_pack"


def test_discover_base_mesh_items_keeps_trio_mesh_entries_separate(tmp_path: Path):
    archive_path = _write_zip(
        tmp_path / "fbx.zip",
        {
            "fbx/多款基础人体模型.fbx": b"main",
            "fbx/赠送.fbx": b"bonus",
            "fbx/素材说明/readme.txt": b"skip",
        },
    )

    items = discover_base_mesh_items("BM-002", archive_path)

    assert len(items) == 2
    assert {item["variant_id"] for item in items} == {"多款基础人体模型", "赠送"}
    assert {item["attempted_format"] for item in items} == {"fbx"}
    assert len({item["item_id"] for item in items}) == 2


def test_discover_base_mesh_items_prefers_fbx_for_major_variants(tmp_path: Path):
    archive_path = _write_zip(
        tmp_path / "A010.zip",
        {
            "root/合集/Art_Boy/Art_Boy.fbx": b"fbx",
            "root/合集/Art_Boy/Boy.obj": b"obj",
            "root/合集/Art_Girl/Girl.obj": b"girl-obj",
            "root/合集/Art_Miss/Art_Miss.fbx": b"miss-fbx",
            "root/合集/body.obj": b"ignored-root",
        },
    )

    items = discover_base_mesh_items("BM-004", archive_path)

    assert [item["variant_id"] for item in items] == ["Art_Boy", "Art_Girl", "Art_Miss"]
    assert next(item for item in items if item["variant_id"] == "Art_Boy")["attempted_format"] == "fbx"
    assert next(item for item in items if item["variant_id"] == "Art_Girl")["attempted_format"] == "obj"
    assert next(item for item in items if item["variant_id"] == "Art_Girl")["format_fallback_used"] is True


def test_ue_suitability_signal_respects_bodypaint_and_ue_smoke():
    assert ue_suitability_signal(
        attempted_format="c4d",
        status="blocked",
        bodypaint_handoff_candidate=False,
        provider_ready_status="",
    ) == "unsupported_format"
    assert ue_suitability_signal(
        attempted_format="fbx",
        status="pass",
        bodypaint_handoff_candidate=True,
        provider_ready_status="pass",
        ue_smoke_status="pass",
    ) == "strong_candidate"
    assert ue_suitability_signal(
        attempted_format="obj",
        status="pass",
        bodypaint_handoff_candidate=False,
        provider_ready_status="pass",
    ) == "partial_candidate"
