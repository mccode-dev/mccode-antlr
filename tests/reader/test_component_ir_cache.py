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


@pytest.fixture(autouse=True)
def sidecars_enabled(monkeypatch):
    """The disk level is opt-in (cache.component_ir); these tests exercise it."""
    monkeypatch.setattr('mccode_antlr.reader.reader.component_ir_enabled', lambda: True)


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


PARENT = "DEFINE COMPONENT Pa\nSETTING PARAMETERS (width=1.0)\nTRACE %{ %}\nEND\n"
CHILD = "DEFINE COMPONENT Ch INHERIT Pa\nEND\n"


@pytest.fixture
def inherit_dir(tmp_path) -> Path:
    (tmp_path / "Pa.comp").write_text(PARENT)
    (tmp_path / "Ch.comp").write_text(CHILD)
    component_cache.clear()
    return tmp_path


def _child_width(directory: Path, *load_first: str) -> str:
    from mccode_antlr.reader.reader import Reader
    from mccode_antlr.reader.registry import LocalRegistry
    reader = Reader(registries=[LocalRegistry("t", str(directory))])
    for name in load_first:
        reader.get_component(name)
    return str(reader.get_component("Ch").setting[0].value)


def _edit_parent(directory: Path):
    import os
    parent = directory / "Pa.comp"
    stat = parent.stat()
    parent.write_text(PARENT.replace("1.0", "2.0"))
    # a distinct mtime even on filesystems with coarse timestamps
    os.utime(parent, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))


@pytest.mark.parametrize("load_first", [(), ("Pa",)])
def test_editing_an_inherit_parent_invalidates_the_child_in_memory(inherit_dir, load_first):
    assert _child_width(inherit_dir, *load_first) == "1.0"
    _edit_parent(inherit_dir)
    assert _child_width(inherit_dir, *load_first) == "2.0"


@pytest.mark.parametrize("load_first", [(), ("Pa",)])
def test_editing_an_inherit_parent_invalidates_the_child_sidecar(inherit_dir, load_first):
    assert _child_width(inherit_dir, *load_first) == "1.0"
    assert component_ir_path(inherit_dir / "Ch.comp").is_file()
    _edit_parent(inherit_dir)
    component_cache.clear()  # as a new process would start
    assert _child_width(inherit_dir, *load_first) == "2.0"


def test_a_copied_tree_keeps_its_sidecars(inherit_dir, tmp_path_factory):
    import shutil
    _child_width(inherit_dir)
    copy = tmp_path_factory.mktemp("copy") / "tree"
    shutil.copytree(inherit_dir, copy)  # copy2: mtimes preserved, like cp -a
    assert component_cache.get(copy / "Ch.comp") is not None  # sidecar hit, no parse


def test_sidecars_are_off_by_default():
    from mccode_antlr.config import config
    assert not config['cache']['component_ir'].get()


@pytest.mark.parametrize('value, enabled', [
    (True, True), (False, False), (1, True), (0, False), (None, False),
    ('true', True), ('false', False), ('1', True), ('0', False), ('no', False),
])
def test_component_ir_enabled_reads_the_config(value, enabled, monkeypatch):
    from mccode_antlr.config import config
    from mccode_antlr.reader import reader
    monkeypatch.undo()  # drop the autouse override; read the real configuration
    config.resolve()  # a LazyConfig loads its sources on first use
    monkeypatch.setattr(config, 'sources', list(config.sources))  # restored afterwards
    config.set({'cache': {'component_ir': value}})
    assert reader.component_ir_enabled() is enabled


def test_disabled_sidecars_are_neither_written_nor_read(comp_file, monkeypatch):
    monkeypatch.setattr('mccode_antlr.reader.reader.component_ir_enabled', lambda: False)
    sidecar = component_ir_path(comp_file)
    component_cache.put(comp_file, _parse(comp_file))
    assert not sidecar.exists()
    assert component_cache.get(comp_file) is not None  # the in-memory level still works

    # A sidecar left by an enabled run is not trusted while disabled.
    import msgspec
    from mccode_antlr.io.json import to_json
    from mccode_antlr.reader.reader import _Sidecar
    sidecar.write_bytes(msgspec.json.encode(_Sidecar(
        sources={comp_file.name: comp_file.stat().st_mtime_ns},
        ir=msgspec.Raw(to_json(_parse(comp_file))),
    )))
    component_cache.clear()
    assert component_cache.get(comp_file) is None
