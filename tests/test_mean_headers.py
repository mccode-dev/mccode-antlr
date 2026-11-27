"""Data with a 'mean: yes' or 'mean: no' header line, as McCode writes since mccode-dev/McCode#3193,
is read and written. A mean, e.g. polarisation, is combined as a mean, weighted by the counts."""
from textwrap import dedent

import numpy as np
import pytest

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
      Ncount: {ncount}
      Trace: no
      Gravitation: no
      Seed: {seed}
      Directory: a0
      Param: a=1
    end simulation

    begin data
      Date: Mon Jan 1 00:00:00 2024
      type: array_0d
      Source: test_instr (test_instr.instr)
      component: pol
      position: 0 0 1
      title: Polarisation monitor
      Ncount: {ncount}
      mean: {mean}
      filename: pol.dat
      statistics: None
      signal: None
      values: {values}
      xylimits: 0 0 0 0 0 0
      variables: I I_err N
    end data

    begin data
      Date: Mon Jan 1 00:00:00 2024
      type: array_1d(2)
      Source: test_instr (test_instr.instr)
      component: mon
      position: 0 0 1
      title: monitor
      Ncount: {ncount}
      mean: no
      filename: mon.dat
      statistics: X0=1; dX=1;
      signal: Min=1; Max=1; Mean=1;
      values: 2 1 20
      xvar: L
      yvar: (I,I_err)
      xlabel: L
      ylabel: I
      xlimits: 0 2
      variables: L I I_err N
    end data
""")

_DAT = dedent("""\
    # Format: McCode with text headers
    # URL: http://www.mccode.org
    # Creator: McStas 3.x
    # Instrument: test_instr
    # Ncount: {ncount}
    # Trace: no
    # Gravitation: no
    # Seed: {seed}
    # Directory: a0
    # Param: a=1
    # Date: Mon Jan 1 00:00:00 2024
    # type: array_1d(2)
    # Source: test_instr
    # component: pol
    # position: 0 0 1
    # title: Polarisation monitor
    # Ncount: {ncount}
    # mean: {mean}
    # filename: pol.dat
    # statistics: X0=1; dX=1;
    # signal: Min=0.4; Max=0.4; Mean=0.4;
    # values: 0.4 0.01 {n2}
    # xvar: L
    # yvar: (I,I_err)
    # xlabel: L
    # ylabel: P
    # xlimits: 0 2
    # variables: L I I_err N
    0.5 {i} 0.01 {n}
    1.5 {i} 0.01 {n}
""")


def test_sim_mean_read_and_written(tmp_path):
    from mccode_antlr.loader.simfile import SimFile
    sim = SimFile.parse(_SIM.format(ncount=100, seed=1, mean='yes', values='0.4 0.01 100'))
    assert [d.mean for d in sim.data] == ['yes', 'no']
    sim.save(tmp_path / 'mccode.sim')
    text = (tmp_path / 'mccode.sim').read_text()
    assert text.count('  mean: yes\n') == 1 and text.count('  mean: no\n') == 1
    assert SimFile.load(tmp_path / 'mccode.sim') == sim


def test_sim_mean_combined_as_mean():
    from mccode_antlr.loader.simfile import SimFile, combine_mccode_sims
    a = SimFile.parse(_SIM.format(ncount=100, seed=1, mean='yes', values='0.4 0.01 100'))
    b = SimFile.parse(_SIM.format(ncount=300, seed=2, mean='yes', values='0.6 0.01 300'))
    pol = combine_mccode_sims([a, b]).data[0]
    mean, error, counts = (float(v) for v in pol.values.split())
    assert mean == pytest.approx(0.55) and counts == 400
    assert 0 < error < 0.2


def test_sim_mean_and_intensity_not_combined():
    from mccode_antlr.loader.simfile import SimFile, combine_mccode_sims
    a = SimFile.parse(_SIM.format(ncount=100, seed=1, mean='yes', values='0.4 0.01 100'))
    b = SimFile.parse(_SIM.format(ncount=100, seed=2, mean='no', values='0.4 0.01 100'))
    with pytest.raises(RuntimeError):
        combine_mccode_sims([a, b])


def test_dat_mean_combined_as_mean(tmp_path):
    from mccode_antlr.loader.datfile import read_mccode_dat
    for name, ncount, seed, i, n in (('a', 100, 1, 0.4, 50), ('b', 300, 2, 0.6, 150)):
        (tmp_path / f'{name}.dat').write_text(_DAT.format(ncount=ncount, seed=seed, mean='yes', i=i, n=n, n2=2*n))
    both = read_mccode_dat(tmp_path / 'a.dat') + read_mccode_dat(tmp_path / 'b.dat')
    i, e, n = (dict(zip(both.variables, both.values))[k] for k in ('I', 'I_err', 'N'))
    assert np.allclose(i, 0.55) and np.allclose(n, 200)
    assert np.all((e > 0) & (e < 0.2))
    mean, error, counts = (float(v) for v in both.metadata['values'].split())
    assert mean == pytest.approx(0.55) and counts == 400
    assert both.metadata['mean'] == 'yes'


def test_dat_intensity_unchanged(tmp_path):
    """mean: no is combined as before: weighted with the ray counts of the runs"""
    from mccode_antlr.loader.datfile import read_mccode_dat
    for name, ncount, seed, i, n in (('a', 100, 1, 0.4, 50), ('b', 300, 2, 0.6, 150)):
        (tmp_path / f'{name}.dat').write_text(_DAT.format(ncount=ncount, seed=seed, mean='no', i=i, n=n, n2=2*n))
    both = read_mccode_dat(tmp_path / 'a.dat') + read_mccode_dat(tmp_path / 'b.dat')
    rows = dict(zip(both.variables, both.values))
    assert np.allclose(rows['I'], 0.55) and np.allclose(rows['N'], 200)
    assert float(both.metadata['values'].split()[0]) == pytest.approx(1.1)


def test_dat_mean_and_intensity_not_combined(tmp_path):
    from mccode_antlr.loader.datfile import read_mccode_dat
    for name, seed, mean in (('a', 1, 'yes'), ('b', 2, 'no')):
        (tmp_path / f'{name}.dat').write_text(_DAT.format(ncount=100, seed=seed, mean=mean, i=0.4, n=50, n2=100))
    with pytest.raises(RuntimeError):
        read_mccode_dat(tmp_path / 'a.dat') + read_mccode_dat(tmp_path / 'b.dat')
