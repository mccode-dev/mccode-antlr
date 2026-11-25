"""Header lines other than Param, as written by MPI runs (Nodes) and mcmerge (Merged_from),
are kept as themselves, never read as parameters; they survive a write and a combination."""
from textwrap import dedent

_SIM = dedent("""\
    McStas simulation description file for test_instr.
    Date:    Mon Jan 1 00:00:00 2024
    Program: McStas 3.x

    begin instrument: test_instr
      File: a0/mccode
      Source: test_instr.instr
      Parameters:  a
      Trace_enabled: yes
      Default_main: yes
      Embedded_runtime: yes
    end instrument

    begin simulation: a0
      Format: McCode with text headers
      URL: http://www.mccode.org
      Creator: McStas 3.x
      Instrument: test_instr.instr
      Ncount: 40000
      Trace: no
      Gravitation: no
      Seed: -1
      Directory: a0
    {extra}  Param: a=1
    end simulation
""")

_MERGED = dedent("""\
      Merged_from: a0 (ASCII), Ncount 20000, Seed 100, Nodes 1
      Merged_from: a1 (ASCII), Ncount 20000, Seed 101, Nodes 1
""")

_DAT = dedent("""\
    # Format: McCode with text headers
    # URL: http://www.mccode.org
    # Creator: McStas 3.x
    # Instrument: test_instr
    # Ncount: 40000
    # Trace: no
    # Gravitation: no
    # Seed: -1
    # Directory: a0
    {extra}# Param: a=1
    # Date: Mon Jan 1 00:00:00 2024
    # type: array_1d(2)
    # Source: test_instr
    # component: mon
    # position: 0 0 1
    # title: monitor
    # Ncount: 40000
    # filename: mon.dat
    # statistics: X0=1; dX=1;
    # signal: Min=1; Max=1; Mean=1;
    # values: 2 1 20
    # xvar: L
    # yvar: (I,I_err)
    # xlabel: L
    # ylabel: Intensity
    # xlimits: 1 2
    # variables: L I I_err N
    1 1 0.1 10
    2 1 0.1 10
""")

_MERGED_LINES = ['a0 (ASCII), Ncount 20000, Seed 100, Nodes 1', 'a1 (ASCII), Ncount 20000, Seed 101, Nodes 1']


def test_sim_keeps_merged_from_and_nodes_out_of_params(tmp_path):
    from mccode_antlr.loader.simfile import SimFile, combine_mccode_sims
    sim = SimFile.parse(_SIM.format(extra='  Nodes: 2\n' + _MERGED)).simulation
    assert sim.Params == ['a=1']
    assert sim.extra == {'Nodes': ['2'], 'Merged_from': _MERGED_LINES}

    SimFile.parse(_SIM.format(extra=_MERGED)).save(tmp_path / 'mccode.sim')
    text = (tmp_path / 'mccode.sim').read_text()
    assert 'Param: Merged_from' not in text and text.count('  Merged_from: ') == 2
    assert SimFile.load(tmp_path / 'mccode.sim').simulation.extra == {'Merged_from': _MERGED_LINES}

    # combining a merged run with a plain repeat keeps the provenance once
    both = combine_mccode_sims([SimFile.parse(_SIM.format(extra=_MERGED)), SimFile.parse(_SIM.format(extra=''))])
    assert both.simulation.Params == ['a=1'] and both.simulation.extra == {'Merged_from': _MERGED_LINES}


def test_dat_keeps_every_merged_from_line(tmp_path):
    from mccode_antlr.loader.datfile import read_mccode_dat, write_combined_mccode_dats
    (tmp_path / 'merged.dat').write_text(_DAT.format(extra=''.join(f'# Merged_from: {m}\n' for m in _MERGED_LINES)))
    (tmp_path / 'plain.dat').write_text(_DAT.format(extra=''))
    merged = read_mccode_dat(tmp_path / 'merged.dat')
    assert merged['Merged_from'] == _MERGED_LINES
    assert dict(merged.parameters) == {'a': '1'}

    write_combined_mccode_dats([tmp_path / 'merged.dat', tmp_path / 'plain.dat'], tmp_path / 'both.dat')
    text = (tmp_path / 'both.dat').read_text()
    assert text.count('# Merged_from: ') == 2
    assert text.index('# Directory:') < text.index('# Merged_from:') < text.index('# Param:')
    assert read_mccode_dat(tmp_path / 'both.dat')['Merged_from'] == _MERGED_LINES
