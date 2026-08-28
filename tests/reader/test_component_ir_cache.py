"""The on-disk component IR cache (`{name}.comp.<salt>.json`).

The salt binds a sidecar to the mccode-antlr build that wrote it, so a parser
or schema change (e.g. issue #321) does not leave users trusting a stale
sidecar after an upgrade.
"""
from pathlib import Path

import pytest

from mccode_antlr.reader.reader import (
    _ComponentCache,
    component_cache,
    component_ir_path,
    component_ir_comp_path,
    component_ir_is_current,
    iter_component_ir_paths,
)

MINIMAL = "DEFINE COMPONENT IrCacheProbe\nTRACE %{ %}\nEND\n"


@pytest.fixture
def comp_file(tmp_path) -> Path:
    p = tmp_path / "IrCacheProbe.comp"
    p.write_text(MINIMAL)
    component_cache.clear()
    return p


def _parse(comp_file: Path):
    from mccode_antlr.comp import Comp
    from mccode_antlr.grammar import McComp_ErrorListener
    from mccode_antlr.reader.reader import make_reader_error_listener
    listener = make_reader_error_listener(
        McComp_ErrorListener, "Component", comp_file.stem, comp_file.read_text()
    )
    return Comp.from_source(None, listener, comp_file.read_text(), str(comp_file), str(comp_file))


def test_sidecar_name_carries_the_build_salt(comp_file):
    sidecar = component_ir_path(comp_file)
    assert sidecar.parent == comp_file.parent
    assert sidecar.name.startswith("IrCacheProbe.comp.")
    assert sidecar.name.endswith(".json")
    assert sidecar.name != "IrCacheProbe.comp.json"  # not the pre-salt scheme
    assert component_ir_comp_path(sidecar) == comp_file
    assert component_ir_is_current(sidecar)


def test_put_writes_the_salted_sidecar_and_get_reads_it(comp_file):
    component_cache.put(comp_file, _parse(comp_file))
    assert component_ir_path(comp_file).is_file()

    component_cache.clear()  # drop the in-memory level
    restored = component_cache.get(comp_file)
    assert restored is not None and restored.name == "IrCacheProbe"


def test_foreign_sidecars_are_ignored_and_pruned(comp_file):
    legacy = comp_file.with_suffix(".comp.json")
    other_build = comp_file.with_suffix(".comp.0123456789ab.json")
    legacy.write_text("{}")
    other_build.write_text("{}")

    # A foreign sidecar must not satisfy a lookup ...
    component_cache.clear()
    assert component_cache.get(comp_file) is None

    # ... and writing this build's sidecar prunes the foreign ones.
    component_cache.put(comp_file, _parse(comp_file))
    assert not legacy.exists()
    assert not other_build.exists()
    assert component_ir_path(comp_file).is_file()


def test_iter_component_ir_paths_finds_every_scheme(tmp_path):
    (tmp_path / "sub").mkdir()
    made = {
        tmp_path / "A.comp.json",
        tmp_path / "A.comp.0123456789ab.json",
        tmp_path / "sub" / "B.comp.cccccccccccc.json",
    }
    for p in made:
        p.write_text("{}")
    (tmp_path / "A.comp").write_text(MINIMAL)  # not a sidecar
    (tmp_path / "notes.json").write_text("{}")  # unrelated

    assert set(iter_component_ir_paths(tmp_path)) == made
