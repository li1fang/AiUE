from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
T1_ROOT = REPO_ROOT / "tools" / "t1" / "python"
CORE_ROOT = REPO_ROOT / "core" / "python"
for candidate in (T1_ROOT, CORE_ROOT):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from aiue_t1.bodypaint_candidate_pool import (  # noqa: E402
    LocalConversionEntry,
    ToyYardCharacterCandidate,
    build_conversion_indexes,
    choose_best_entry,
    match_candidate_to_entry,
    toy_yard_package_key,
    toy_yard_sample_key,
)


def _candidate() -> ToyYardCharacterCandidate:
    return ToyYardCharacterCandidate(
        package_db_id=1,
        sample_db_id=2,
        canonical_package_id="pkg_mingchao-sample-4f64c1a1-character-d214086d_7d8f416608",
        canonical_sample_id="sample_mingchao-sample-4f64c1a1_d47fa08f39",
        display_name="凯茜娅-贴身特助（黑丝版）",
        source_game="mingchao",
        package_role="character",
        warehouse_status="ready_for_pipeline",
    )


def test_toy_yard_keys_match_current_conversion_sample_shapes():
    assert toy_yard_sample_key("sample_mingchao-1742887197777-597530c2_7938dc4570") == "mingchao_1742887197777_597530c2_7938dc4570"
    assert toy_yard_sample_key("sample_mingchao-sample-4f64c1a1_d47fa08f39").startswith("mingchao_sample_4f64c1a1")
    assert toy_yard_package_key("pkg_mingchao-sample-4f64c1a1-character-d214086d_7d8f416608").startswith("mingchao_sample_4f64c1a1_character")


def test_choose_best_entry_prefers_non_e2e_root():
    root_entry = LocalConversionEntry(
        manifest_path=Path(r"C:\AiUE\local\conversion_out\mingchao\1742887197777\manifest.json"),
        mesh_path=Path(r"C:\AiUE\local\conversion_out\mingchao\1742887197777\坎特蕾拉.fbx"),
        sample_key="mingchao_1742887197777_597530c2",
        package_key="",
        display_key="坎特蕾拉",
        score=1000,
    )
    e2e_entry = LocalConversionEntry(
        manifest_path=Path(r"C:\AiUE\local\conversion_out\mingchao\_e2e_runs\smoke\20260408T171446Z\conversion\1742887197777\manifest.json"),
        mesh_path=Path(r"C:\AiUE\local\conversion_out\mingchao\_e2e_runs\smoke\20260408T171446Z\conversion\1742887197777\坎特蕾拉.fbx"),
        sample_key="mingchao_1742887197777_597530c2",
        package_key="",
        display_key="坎特蕾拉",
        score=50,
    )
    assert choose_best_entry([e2e_entry, root_entry]) == root_entry


def test_match_candidate_prefers_sample_key_then_display_name():
    candidate = _candidate()
    sample_match = LocalConversionEntry(
        manifest_path=Path(r"C:\AiUE\local\conversion_out\mingchao\_e2e_runs\stress\20260408T172104Z\conversion\【尘白禁区】凯茜娅-贴身特助\【尘白禁区】凯茜娅-贴身特助\【尘白禁区】凯茜娅-贴身特助\manifest.json"),
        mesh_path=Path(r"C:\AiUE\local\conversion_out\mingchao\_e2e_runs\stress\20260408T172104Z\conversion\【尘白禁区】凯茜娅-贴身特助\【尘白禁区】凯茜娅-贴身特助\【尘白禁区】凯茜娅-贴身特助\凯茜娅-贴身特助（黑丝版）.fbx"),
        sample_key="mingchao_sample_4f64c1a1",
        package_key="",
        display_key="凯茜娅_贴身特助_黑丝版",
        score=100,
    )
    display_only = LocalConversionEntry(
        manifest_path=Path(r"C:\AiUE\local\conversion_out\mingchao\misc\manifest.json"),
        mesh_path=Path(r"C:\AiUE\local\conversion_out\mingchao\misc\凯茜娅-贴身特助（黑丝版）.fbx"),
        sample_key="",
        package_key="",
        display_key="凯茜娅_贴身特助_黑丝版",
        score=10,
    )
    entry, strategy = match_candidate_to_entry(candidate, build_conversion_indexes([display_only, sample_match]))
    assert entry == sample_match
    assert strategy == "sample_key"
