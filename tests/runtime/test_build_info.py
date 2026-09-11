"""Build information as it reaches an actual compiled binary.

The generated-C shape is covered in tests/test_build_info.py; these tests check
that it survives the C compiler, that the preprocessor decides the target, and
that scanning the binary and asking it agree.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from mccode_antlr import Flavor
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.test import compiled_test, mpi_compiled_test

INSTR = """DEFINE INSTRUMENT bldinf(dummy=0)
TRACE
COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE
END
"""

# An instrument that mentions MPI_Init in a guarded block. Compiled serially with
# --source the text is embedded verbatim, which is what made the old symbol scan
# report a serial binary as an MPI one.
LOOKS_LIKE_MPI = """DEFINE INSTRUMENT looksmpi(dummy=0)
TRACE
COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE
SAVE %{
#ifdef USE_MPI
  MPI_Init(NULL, NULL);
  MPI_Barrier(MPI_COMM_WORLD);
#endif
%}
END
"""


def build(directory, source=INSTR, **kwargs):
    from mccode_antlr.run.runner import mccode_compile
    instr = parse_mcstas_instr(source)
    binary, target = mccode_compile(instr, Path(directory), flavor=Flavor.MCSTAS, **kwargs)
    return instr, binary


@compiled_test
def test_a_serial_binary_says_so():
    from mccode_antlr.build_info import probe_binary, read_build_info
    from mccode_antlr.instr.digest import instrument_digest
    with TemporaryDirectory() as directory:
        instr, binary = build(directory)
        info = read_build_info(binary)
        assert info is not None, 'no build information found in the compiled binary'
        assert (info['mpi'], info['acc'], info['nexus']) == (False, False, False)
        assert info['instrument'] == 'bldinf'
        assert info['source_hash'] == instrument_digest(instr)
        assert probe_binary(binary, allow_exec=False).origin == 'metadata'


@compiled_test
def test_the_binary_and_the_scan_agree():
    """--meta-data is the authoritative reading; the scan must match it exactly."""
    from mccode_antlr.build_info import (BUILD_INFO_NAME, query_binary_metadata,
                                         read_build_info)
    with TemporaryDirectory() as directory:
        _, binary = build(directory)
        answered = query_binary_metadata(binary, BUILD_INFO_NAME, 'bldinf')
        assert answered is not None, '--meta-data did not return the entry'
        assert json.loads(answered) == read_build_info(binary)


@compiled_test
def test_the_entry_is_reachable_like_any_other_metadata():
    """It is an ordinary METADATA entry, so the ordinary query flags find it.

    --meta-list is deliberately not exercised: metadata_table_print_all_components
    in the McCode runtime's metadata-r.c aliases two buffers ("line=linetmp") and
    then frees both, so it aborts on a double free regardless of what the table
    contains. That predates this change -- a binary built before it, with an empty
    table, aborts the same way.
    """
    from subprocess import run
    from mccode_antlr.build_info import BUILD_INFO_NAME
    with TemporaryDirectory() as directory:
        _, binary = build(directory)
        defined = run([str(binary), '--meta-defined', 'bldinf'], capture_output=True)
        assert BUILD_INFO_NAME in defined.stdout.decode()
        typed = run([str(binary), '--meta-type', f'bldinf:{BUILD_INFO_NAME}'],
                    capture_output=True)
        assert typed.stdout.decode().strip() == 'application/json'


@compiled_test
def test_symbol_names_no_longer_fool_the_probe():
    from mccode_antlr.build_info import probe_binary
    from mccode_antlr.compiler.c import CBinaryTarget, infer_binary_target
    from mccode_antlr.reader import Reader
    from mccode_antlr.reader.registry import collect_local_registries
    from mccode_antlr.run.runner import mccode_compile
    with TemporaryDirectory() as directory:
        # Embedding needs a real file on disk, and a real file is what makes the
        # MPI_Init text land in the binary in the first place.
        source = Path(directory) / 'looksmpi.instr'
        source.write_text(LOOKS_LIKE_MPI)
        reader = Reader(registries=collect_local_registries(Flavor.MCSTAS, None))
        instr = reader.get_instrument(source)
        binary, _ = mccode_compile(instr, Path(directory), flavor=Flavor.MCSTAS,
                                   config={'embed_instrument_file': True})
        assert binary.read_bytes().find(b'MPI_Init') != -1, 'precondition: the text is there'
        assert probe_binary(binary, allow_exec=False).mpi is False
        assert not (infer_binary_target(binary).type & CBinaryTarget.Type.mpi)


@compiled_test
def test_a_rebuild_is_skipped_and_an_edit_is_not():
    from mccode_antlr.run.runner import mccode_compile
    with TemporaryDirectory() as directory:
        _, binary = build(directory)
        first = binary.stat().st_mtime_ns

        again, _ = mccode_compile(parse_mcstas_instr(INSTR), Path(directory),
                                  flavor=Flavor.MCSTAS)
        assert again == binary and again.stat().st_mtime_ns == first

        edited = parse_mcstas_instr(INSTR.replace('AT (0,0,0)', 'AT (0,0,1)'))
        third, _ = mccode_compile(edited, Path(directory), flavor=Flavor.MCSTAS)
        assert third == binary and third.stat().st_mtime_ns != first


@compiled_test
def test_a_damaged_binary_is_rebuilt_rather_than_reused():
    """Previously any file at the path was accepted, however broken."""
    from mccode_antlr.run.runner import mccode_compile
    with TemporaryDirectory() as directory:
        _, binary = build(directory)
        binary.write_bytes(b'not a binary at all')
        again, _ = mccode_compile(parse_mcstas_instr(INSTR), Path(directory),
                                  flavor=Flavor.MCSTAS)
        assert again == binary and binary.read_bytes() != b'not a binary at all'


@mpi_compiled_test
def test_an_mpi_binary_says_so_and_gets_its_own_name():
    from mccode_antlr.build_info import read_build_info
    with TemporaryDirectory() as directory:
        _, serial = build(directory)
        _, parallel = build(directory, target={'mpi': True})
        assert serial != parallel, 'the two targets must not share a cache slot'
        assert parallel.name.endswith(f'.mpi{serial.suffix}')
        assert serial.exists() and parallel.exists()
        assert read_build_info(serial)['mpi'] is False
        assert read_build_info(parallel)['mpi'] is True


@mpi_compiled_test
def test_the_preprocessor_decides_not_the_translation():
    """A .c translated without knowing the target, compiled for MPI, records MPI.

    This is the property that makes the record trustworthy for the
    `mcstas-antlr foo.instr` then `mcc-antlr --parallel foo.c` workflow.
    """
    from mccode_antlr.build_info import read_build_info
    from mccode_antlr.compiler.c import CBinaryTarget, compile_c_file, instrument_source
    with TemporaryDirectory() as directory:
        instr = parse_mcstas_instr(INSTR)
        source = Path(directory) / 'bldinf.c'
        source.write_text(instrument_source(
            instr, flavor=Flavor.MCSTAS,
            config=dict(default_main=True, enable_trace=False, portable=False,
                        include_runtime=True, embed_instrument_file=False)))
        assert 'MCCODE_ANTLR_BUILD_MPI' in source.read_text(), 'still undecided in the .c'

        binary = compile_c_file(source, CBinaryTarget(mpi=True),
                                output=Path(directory), replace=True)
        assert read_build_info(binary)['mpi'] is True
        assert binary.name.endswith(f'.mpi{binary.suffix}')


@compiled_test
def test_the_build_info_cli_flag_reports_a_binary():
    from subprocess import run
    import sys
    with TemporaryDirectory() as directory:
        _, binary = build(directory)
        result = run([sys.executable, '-c',
                      'from mccode_antlr.run.runner import mcstas_cmd; mcstas_cmd()',
                      '--build-info', str(binary)], capture_output=True)
        assert result.returncode == 0, result.stderr.decode()
        assert json.loads(result.stdout.decode())['instrument'] == 'bldinf'
