from io import StringIO


def test_codegen_header_replacement_rewrites_bad_include(monkeypatch):
    import mccode_antlr.reader as reader_mod
    import mccode_antlr.translators.c as c_mod

    class DummyCodegenRegistry:
        def known(self, name):
            return name == "windirent.h"

        def contents(self, name):
            return "/* vendored windirent */\nint dirent_dummy;\n"

    monkeypatch.setattr(reader_mod, "codegen_registries", lambda: [DummyCodegenRegistry()])

    replacement = c_mod.codegen_header_file_replacement("windirent.h")
    assert replacement is not None

    source = "#include <windirent.h>\nint keep_me;\n"
    patched = replacement.filter(source)

    assert "#include <windirent.h>" not in patched
    assert "vendored windirent" in patched
    assert "int keep_me;" in patched


def test_mccode_r_c_replacement_non_windows_returns_none(monkeypatch):
    import platform
    import mccode_antlr.translators.c as c_mod
    import mccode_antlr.reader.registry as registry_mod

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(registry_mod, "mccode_registry_version", lambda: (_ for _ in ()).throw(RuntimeError("should not be called")))

    assert c_mod.mccode_r_c_replacement() is None


def test_mccode_r_c_replacement_windows_old_version_returns_none(monkeypatch):
    from packaging.version import Version
    import platform
    import mccode_antlr.translators.c as c_mod
    import mccode_antlr.reader.registry as registry_mod

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(registry_mod, "mccode_registry_version", lambda: Version("3.6.8"))

    assert c_mod.mccode_r_c_replacement() is None


def test_mccode_r_c_replacement_windows_mid_version_logs_and_returns_none(monkeypatch):
    from packaging.version import Version
    import platform
    import mccode_antlr.translators.c as c_mod
    import mccode_antlr.reader.registry as registry_mod

    class DummyLogger:
        def __init__(self):
            self.messages = []

        def info(self, msg):
            self.messages.append(msg)

    logger = DummyLogger()
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(c_mod, "logger", logger)
    monkeypatch.setattr(registry_mod, "mccode_registry_version", lambda: Version("3.7.5"))

    assert c_mod.mccode_r_c_replacement() is None
    assert any("dirent.h" in message for message in logger.messages)


def test_mccode_r_c_replacement_windows_new_version_returns_file_replacement(monkeypatch):
    from packaging.version import Version
    import platform
    import mccode_antlr.translators.c as c_mod
    import mccode_antlr.reader.registry as registry_mod

    sentinel = object()
    called = {}

    def fake_codegen_header_file_replacement(name):
        called["name"] = name
        return sentinel

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(c_mod, "codegen_header_file_replacement", fake_codegen_header_file_replacement)
    monkeypatch.setattr(registry_mod, "mccode_registry_version", lambda: Version("3.7.6"))

    assert c_mod.mccode_r_c_replacement() is sentinel
    assert called["name"] == "windirent.h"


def test_embed_file_applies_mccode_r_c_replacement_pattern(tmp_path):
    import re
    from mccode_antlr import Flavor
    from mccode_antlr.translators.target import TargetVisitor, FileReplacement

    runtime_file = tmp_path / "mccode-r.c"
    runtime_file.write_text('#include <windirent.h>\nint keep_me;\n')

    class DummyInstr:
        name = "dummy"
        registries = []
        components = []

        def verify_instance_parameters(self):
            return None

    class DummyVisitor(TargetVisitor):
        def library_path(self, filename=None):
            if filename == "mccode-r.c":
                return runtime_file
            raise RuntimeError(f"Unexpected filename: {filename}")

    visitor = DummyVisitor(DummyInstr(), Flavor.MCSTAS)
    visitor.output = StringIO()
    visitor.file_replacements["mccode-r.c"] = FileReplacement(
        re.compile(r'^\s*#\s*include\s*<\s*windirent(?:\.h)?\s*>\s*$', re.MULTILINE),
        "/* vendored windirent */",
    )

    visitor.embed_file("mccode-r.c")
    output = visitor.output.getvalue()

    assert '#include <windirent.h>' not in output
    assert 'vendored windirent' in output
    assert 'int keep_me;' in output


def test_file_replacement_preserves_literal_escape_sequences():
    """FileReplacement.filter() should preserve backslashes in literal C code like '\0' and '\\\\'."""
    import re
    from mccode_antlr.translators.target import FileReplacement

    # Simulate header content with actual escape sequences
    header_with_escapes = (
        '/* windirent.h */\n'
        'char escape_null = \'\\0\';\n'
        'char backslash_char = \'\\\\\';\n'
        'const char *str = "line1\\nline2";\n'
    )

    # Pattern matches the include line
    pattern = re.compile(
        r'^\s*#\s*include\s*<\s*windirent(?:\.h)?\s*>\s*$',
        flags=re.MULTILINE,
    )

    # Create replacement that includes literal escape sequences
    replacement = FileReplacement(pattern, header_with_escapes)

    source = '#include <windirent.h>\nint x;'
    result = replacement.filter(source)

    # All escape sequences must be preserved
    assert '\\0' in result, f"Lost null escape: {result}"
    assert '\\\\' in result, f"Lost backslash escape: {result}"
    assert '\\n' in result, f"Lost newline escape: {result}"
    # Original content should still be there
    assert 'int x;' in result
