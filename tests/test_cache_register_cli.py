"""Tests for `mccode-antlr cache register`, which mints a pooch registry file
(path + sha256 hash per line) from a local directory tree.
"""
import pytest
from pooch import file_hash

from mccode_antlr.cli.cache import build_registry, cache_register


def _make_tree(tmp_path):
    """Build a small directory tree to register.

    tmp_path/
        root/
            dir1/
                a.comp
                b.txt
                nested/
                    c.comp
            dir2/
                d.comp
    """
    root = tmp_path / "root"
    (root / "dir1" / "nested").mkdir(parents=True)
    (root / "dir2").mkdir(parents=True)

    (root / "dir1" / "a.comp").write_text("a")
    (root / "dir1" / "b.txt").write_text("b")
    (root / "dir1" / "nested" / "c.comp").write_text("c")
    (root / "dir2" / "d.comp").write_text("d")

    return root


def test_build_registry_hashes_matching_files(tmp_path):
    root = _make_tree(tmp_path)

    hashes = build_registry(root, ["dir1", "dir2"])

    expected_keys = {"dir1/a.comp", "dir1/b.txt", "dir1/nested/c.comp", "dir2/d.comp"}
    assert set(hashes.keys()) == expected_keys
    for rel, digest in hashes.items():
        assert digest == file_hash(str(root / rel))


def test_build_registry_ext_filter(tmp_path):
    root = _make_tree(tmp_path)

    hashes = build_registry(root, ["dir1", "dir2"], ext=[".comp"])

    assert set(hashes.keys()) == {"dir1/a.comp", "dir1/nested/c.comp", "dir2/d.comp"}


def test_build_registry_non_recursive(tmp_path):
    root = _make_tree(tmp_path)

    hashes = build_registry(root, ["dir1"], recursive=False)

    assert set(hashes.keys()) == {"dir1/a.comp", "dir1/b.txt"}


def test_cache_register_writes_sorted_registry_file(tmp_path, capsys):
    root = _make_tree(tmp_path)
    out = tmp_path / "out" / "registry.txt"

    cache_register(root=str(root), dirs=["dir1", "dir2"], out=str(out))

    lines = out.read_text().splitlines()
    assert lines == sorted(lines)

    expected = build_registry(root, ["dir1", "dir2"])
    parsed = dict(line.split(" ", 1) for line in lines)
    assert parsed == expected
    for digest in parsed.values():
        assert len(digest) == 64
        assert digest == digest.lower()

    out_msg = capsys.readouterr().out
    assert f"Wrote {len(expected)} entries" in out_msg


def test_cache_register_missing_root_exits_nonzero(tmp_path, capsys):
    missing = tmp_path / "does-not-exist"

    with pytest.raises(SystemExit) as exc_info:
        cache_register(root=str(missing), dirs=["dir1"], out=str(tmp_path / "out.txt"))

    assert exc_info.value.code == 1
    assert "ERROR: " in capsys.readouterr().out


def test_cache_register_missing_dir_warns_but_succeeds(tmp_path, capsys):
    root = _make_tree(tmp_path)
    out = tmp_path / "out.txt"

    cache_register(root=str(root), dirs=["dir1", "does-not-exist"], out=str(out))

    out_msg = capsys.readouterr().out
    assert "WARNING: " in out_msg
    assert "does-not-exist" in out_msg

    lines = out.read_text().splitlines()
    assert {line.split(" ", 1)[0] for line in lines} == {"dir1/a.comp", "dir1/b.txt", "dir1/nested/c.comp"}


def test_build_registry_skips_component_ir_sidecars(tmp_path):
    """Generated IR sidecars are never registered, whichever build wrote them.

    Registering one promises a file no source repository contains -- exactly how
    mcstas-comps/optics/Collimator_linear.comp.json reached the published McCode
    registries and made `cache populate` fail for every tag that carried it.
    """
    root = _make_tree(tmp_path)
    # pre-salt sidecar (the form that actually leaked), and a salted one
    (root / "dir1" / "a.comp.json").write_text("{}")
    (root / "dir2" / "d.comp.8553da4f0f17.json").write_text("{}")

    hashes = build_registry(root, ["dir1", "dir2"])

    assert "dir1/a.comp" in hashes
    assert "dir2/d.comp" in hashes
    assert "dir1/a.comp.json" not in hashes
    assert "dir2/d.comp.8553da4f0f17.json" not in hashes
    assert not any(k.endswith(".json") for k in hashes)


def test_build_registry_keeps_unrelated_json(tmp_path):
    """Only the IR sidecar spelling is skipped -- other JSON is ordinary content."""
    root = _make_tree(tmp_path)
    (root / "dir1" / "data.json").write_text("{}")
    (root / "dir1" / "thing.instr.json").write_text("{}")

    hashes = build_registry(root, ["dir1", "dir2"])

    assert "dir1/data.json" in hashes
    assert "dir1/thing.instr.json" in hashes


def test_cache_register_omits_sidecars_from_output(tmp_path, capsys):
    """The minted file contains no sidecar, and the skip is reported."""
    root = _make_tree(tmp_path)
    (root / "dir1" / "a.comp.json").write_text("{}")
    out = tmp_path / "pooch-registry.txt"

    cache_register(str(root), ["dir1", "dir2"], out=str(out))

    text = out.read_text()
    assert "dir1/a.comp " in text
    assert "a.comp.json" not in text
    assert "skipped 1 generated component IR sidecar" in capsys.readouterr().out
