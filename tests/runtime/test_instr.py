from unittest import TestCase
from loguru import logger
from mccode_antlr.test import compiled_test, mcpl_compiled_test
from mccode_antlr.utils import compile_and_run
from mccode_antlr import Flavor

class TestCompiledInstr(TestCase):
    @compiled_test
    def test_one_axis(self):
        from math import pi, asin, sqrt
        from mccode_antlr.loader import parse_mcstas_instr
        d_spacing = 3.355  # (002) for Highly-ordered Pyrolytic Graphite
        mean_energy = 5.0
        energy_width = 0.5
        mean_ki = sqrt(mean_energy / 2.0722)
        instr = f"""
        DEFINE INSTRUMENT splitRunTest(a1=0, a2=0, virtual_source_x=0.05, virtual_source_y=0.1, string newname)
        TRACE
        COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
        COMPONENT source = Source_simple(yheight=2*virtual_source_y, xwidth=0.2, dist=1.5, focus_xw=0.06, focus_yh=0.12,
                                         E0={mean_energy}, dE={energy_width})
                           AT (0, 0, 0) RELATIVE origin
        COMPONENT m0 = PSD_monitor(xwidth=0.1, yheight=0.15, nx=100, ny=160, restore_neutron=1) AT (0, 0, 0.01) RELATIVE PREVIOUS
        COMPONENT guide = Guide_gravity(w1 = 0.06, h1 = 0.12, w2 = 0.05, h2 = 0.1, l = 30, m = 4) 
                          AT (0, 0, 1.5) RELATIVE  PREVIOUS
        COMPONENT guide_end = Arm() AT (0, 0, 30) RELATIVE PREVIOUS
        COMPONENT m1 = PSD_monitor(xwidth=0.1, yheight=0.15, nx=100, ny=160, restore_neutron=1) AT (0, 0, 0.01) RELATIVE PREVIOUS
        COMPONENT aperture = Slit(xwidth=virtual_source_x, yheight=virtual_source_y) AT (0, 0, 0.01) RELATIVE PREVIOUS
        COMPONENT split_at = Arm() AT (0, 0, 0.0001) RELATIVE PREVIOUS
        COMPONENT m3 = PSD_monitor(xwidth=0.1, yheight=0.15, nx=100, ny=160, restore_neutron=1) AT (0, 0, 0.01) RELATIVE PREVIOUS
        COMPONENT mono_point = Arm() AT (0, 0, 0.8) RELATIVE split_at
        METADATA "txt" "something" %{{
            This is some unparsed metadata that will be included as a literal string in the instrument.
        %}}
        COMPONENT mono = Monochromator_curved(zwidth = 0.02, yheight = 0.02, NH = 13, NV = 7, DM={d_spacing}) 
                         AT (0, 0, 0) RELATIVE  mono_point ROTATED (0, a1, 0) RELATIVE mono_point
        COMPONENT sample_arm = Arm() AT (0, 0, 0) RELATIVE mono_point ROTATED (0, a2, 0) RELATIVE mono_point
        COMPONENT detector = Monitor(xwidth=0.1, yheight=0.15, restore_neutron=1) AT (0, 0, 0.8) RELATIVE sample_arm
        COMPONENT lmon = L_monitor(filename=newname) AT (0, 0, 0.001) RELATIVE PREVIOUS
        END
        """
        instr = parse_mcstas_instr(instr)

        a1 = asin(pi / d_spacing / mean_ki) * 180 / pi
        self.assertAlmostEqual(a1, 37.0722, 4)
        parameters = f'a1={a1} a2={2 * a1} -n 1000000'

        std_output, dats = compile_and_run(instr, parameters)
        self.assertEqual(len(dats), 5)
        self.assertEqual(dats['m0'].data.shape, (3, 160, 100))
        self.assertEqual(dats['m1'].data.shape, (3, 160, 100))
        self.assertEqual(dats['m3'].data.shape, (3, 160, 100))
        self.assertEqual(dats['detector'].data.shape, (3, ))

        # Moving farther from the source means less (but finite) intensity in equivalent monitors
        self.assertTrue(sum(sum(dats['m0']['I'])) > sum(sum(dats['m1']['I'])) > sum(sum(dats['m3']['I'])) > 0)
        # The detector has been positioned correctly to collect intensity
        self.assertTrue(dats['detector']['I'] > 0)

    @compiled_test
    def test_assembled_parameters(self):
        """Check that setting an instance parameter to a value that is an instrument parameter name works"""
        from mccode_antlr.assembler import Assembler
        assembler = Assembler('assembled_parameters_test_instr', flavor=Flavor.MCSTAS)
        assembler.parameter("double par0 = 3.14159")
        origin = assembler.component("origin", "Progress_bar", at=[0, 0, 0])
        left = assembler.component('left', 'Slit', at=([0, 0, 1], origin), rotate=[0, 90, 0],
                                   parameters=dict(xwidth='par0', yheight='2*fmod(par0, 0.1)'))

        compile_and_run(assembler.instrument, None, run=False)

    @compiled_test
    def test_vector_component_parameter(self):
        """Some components can use vector parameters, which must be initialized by initializer lists"""
        from mccode_antlr.common import Value
        from mccode_antlr.loader import parse_mcstas_instr
        # TODO Update the registry with the new Conics_* components, then update this test (if necessary)
        instr = """
        DEFINE INSTRUMENT test_vector_component_parameter() TRACE
        COMPONENT cEH = Conics_EH(R0=0.99, alpha=6.07, W=0.003, m=3, nshells=4, focal_length_u=10, focal_length_d=10,
                                  radii={0.05236, 0.03, 0.01, 0.0031416}, le=0.25, lh=0.25, disk=1)
        AT (0,0,0) ABSOLUTE
        COMPONENT cEH2 = Conics_EH(R0=0.99, alpha=6.07, W=0.003, m=3, nshells=0, focal_length_u=10, focal_length_d=10,
                                   le=0.25, lh=0.25, disk=0)
        AT (0,0,1) ABSOLUTE
        END
        """
        instr = parse_mcstas_instr(instr)
        self.assertEqual(instr.components[0].get_parameter('radii').value, Value([0.05236, 0.03, 0.01, 0.0031416]))

        try:
            compile_and_run(instr, '-n 1000', run=True)
        except RuntimeError as e:
            logger.error(f'Failed to compile instrument: {e}')
            self.fail(f'Failed to compile instrument {e}')

    @compiled_test
    def test_split_broken_reference_compiles(self):
        from mccode_antlr.loader import parse_mcstas_instr
        from textwrap import dedent
        instr = parse_mcstas_instr(dedent("""\
        DEFINE INSTRUMENT test_tof(phase/"degree"=0, ang/"degree"=0)
        TRACE
        COMPONENT Origin = Progress_bar() AT (0, 0, 0) ABSOLUTE 
        COMPONENT ESS_source = ESS_butterfly(
            sector="W", beamline=4, yheight=0.03, cold_frac=0.5, dist=1, focus_xw=0.01, focus_yh=0.01, 
            c_performance=1.0, t_performance=1.0, Lmin=1, Lmax=2, tmax_multiplier=1.5, n_pulses=1, acc_power=2.0
        ) AT (0, 0, 0) ABSOLUTE 
        COMPONENT guide = Guide_gravity(w1=0.01, w2=0.05, h1=0.01, h2=0.05, l=8.0, m=3.5, G=-9.82) AT (0, 0, 1) ABSOLUTE 
        COMPONENT guide_end = Arm() AT (0, 0, 8.0) RELATIVE guide
        COMPONENT chopper = DiskChopper(radius=0.35, nu=14, phase=phase, theta_0=115) AT (0, 0, 0.01) RELATIVE guide_end
        COMPONENT rotate = Arm() AT (0, 0, 0) RELATIVE chopper ROTATED (0, ang, 0) RELATIVE chopper
        COMPONENT aperture = Slit(xwidth=0.05, yheight=0.05) AT (0, 0, 1) RELATIVE rotate
        COMPONENT split_at = Arm() AT (0, 0, 1e-08) RELATIVE rotate
        COMPONENT sample = Incoherent(
            radius=0.005, yheight=0.02, thickness=0.001, focus_ah=2.0, focus_aw=2.0, target_x=1.0, target_y=0.0, 
            target_z=0.0, Etrans=0.0, deltaE=0.2
        ) AT (0, 0, 1) RELATIVE aperture
        END"""))
        _, second = instr.split('split_at', remove_unused_parameters=True)
        try:
            compile_and_run(second, '-n 1000 ang=10', run=True)
        except RuntimeError as e:
            logger.error(f'Failed to compile instrument: {e}')
            self.fail(f'Failed to compile instrument {e}')

    @mcpl_compiled_test
    def test_mcpl_split_run(self):
        # Adapted from Test_MCPL_*.instr in ${MCCODE}/mcstas-comps/examples
        from mccode_antlr.instr import Instr
        from mccode_antlr.common import ComponentParameter, Expr
        from mccode_antlr.compiler.c import compile_instrument, run_compiled_instrument, CBinaryTarget
        from mccode_antlr import Flavor
        from mccode_antlr.loader import read_mccode_dat, parse_mcstas_instr
        from tempfile import TemporaryDirectory
        from os import R_OK, access
        from pathlib import Path
        from random import randint
        from numpy import allclose

        instr_source = """
        DEFINE INSTRUMENT Test_MCPL_output()
        USERVARS %{ double flag; %}
        TRACE
        COMPONENT Origin = Progress_bar() AT (0, 0, 0) ABSOLUTE
        COMPONENT sa = Source_Maxwell_3( /* flux in n/s/cm2/st/AA */
                                        Lmin=1, Lmax=11, dist=1, focus_xw=0.1, focus_yh=0.1, xwidth=0.01, yheight=0.01,
                                        T1=216.8,I1=1.24e+13,T2=33.9,I2=1.02e+13, T3=16.7 ,I3=3.0423e+12)
        AT (0,0,0) ABSOLUTE
        EXTEND %{
            t=1e-3*rand01();
            flag=(double)mcget_run_num();
        %}
        COMPONENT split_point = Arm() AT(0,0,0) RELATIVE PREVIOUS
        COMPONENT m1 = Monitor_nD(filename="o1", xwidth=0.2, yheight=0.2,
                                  options="lambda limits=[1 11] bins=100 parallel", bins=40)
        AT (0,0,0) ABSOLUTE
        COMPONENT m2 = Monitor_nD(filename="o2", xwidth=0.2, yheight=0.2, options="x y, parallel", bins=40)
        AT (0,0,0) ABSOLUTE
        COMPONENT m3 = Monitor_nD(filename="o3", xwidth=0.2, yheight=0.2, options="t limits=[0 1e-3]parallel", bins=40)
        AT (0,0,0) ABSOLUTE
        COMPONENT m4 = Monitor_nD(filename="o4", xwidth=0.2, yheight=0.2, options="E limits=[0 82] parallel", bins=40)
        AT (0,0,0) ABSOLUTE
        END
        """
        instr = parse_mcstas_instr(instr_source)
        self.assertEqual(instr.name, 'Test_MCPL_output')

        flag_params = tuple(ComponentParameter(k, Expr.str(v)) for k, v in [
            ('userflag', '"flag"'), ('userflagcomment', '"Neutron Id"')])
        before, after = instr.mcpl_split('split_point', filename='test_mcpl_split', output_parameters=flag_params)
        self.assertEqual(before.name, 'Test_MCPL_output_first')
        self.assertEqual(after.name, 'Test_MCPL_output_second')
        self.assertTrue(isinstance(before, Instr))
        self.assertTrue(isinstance(after, Instr))
        self.assertEqual(len(before.components), 3)
        self.assertEqual(len(after.components), 5)
        for i, name in enumerate(('Origin', 'sa', 'split_point')):
            self.assertEqual(before.components[i].name, name)
        for i, name in enumerate(('split_point', 'm1', 'm2', 'm3', 'm4')):
            self.assertEqual(after.components[i].name, name)

        # If we compile and run the parsed instrument, or the split instrument parts, we should get the same results
        target = CBinaryTarget(mpi=False, acc=False, count=1, nexus=False)
        config = dict(default_main=True, enable_trace=False, portable=False, include_runtime=True,
                      embed_instrument_file=False, verbose=False)
        with TemporaryDirectory() as directory:
            expected_binaries = [Path(directory).joinpath(f'{x.name}.out') for x in (instr, before, after)]
            for obj in (instr, before, after):
                try:
                    compile_instrument(obj, target, directory, flavor=Flavor.MCSTAS, config=config)
                except RuntimeError as e:
                    logger.error(f'Failed to compile instrument: {e}')
                    raise e

            for binary in expected_binaries:
                self.assertTrue(binary.exists())
                self.assertTrue(binary.is_file())
                self.assertTrue(access(binary, R_OK))

            # Run the instrument and check that the output is the same
            seed = randint(1000, 2**32 - 1)
            common = f'--seed {seed} -n 10000'
            run_compiled_instrument(expected_binaries[0], target, f"--dir {directory}/instr {common}")
            mcpl_file = Path(directory).joinpath('instr')
            run_compiled_instrument(expected_binaries[1], target, f"--dir {directory}/before {common} mcpl_filename={mcpl_file}")
            # Breaking change in development McStas -- MCPL_output appends the extension even if it's already there
            # So do not specify it, then add it here.
            if not mcpl_file.exists() or not mcpl_file.is_file():
                mcpl_file = Path(directory).joinpath('instr.mcpl')
            # Depending on how MCPL was built, it might have gzipped the output file
            if not mcpl_file.exists() or not mcpl_file.is_file():
                mcpl_file = Path(directory).joinpath('instr.mcpl.gz')
            self.assertTrue(mcpl_file.exists())
            try:
                run_compiled_instrument(expected_binaries[2], target,
                                        f"--dir {directory}/after {common} mcpl_filename={mcpl_file}")
            except RuntimeError as ex:
                self.fail(str(ex))

            # Now check that the instr and after outputs are the same
            instr_files = list(Path(directory).joinpath('instr').glob('o*'))
            after_files = list(Path(directory).joinpath('after').glob('o*'))
            self.assertEqual(len(instr_files), len(after_files))
            for file in instr_files:
                self.assertEqual(len([x for x in after_files if x.name == file.name]), 1)
            for file in after_files:
                self.assertEqual(len([x for x in instr_files if x.name == file.name]), 1)
            instr_files = [[x for x in instr_files if x.name == file.name][0] for file in after_files]
            for instr_file, after_file in zip(instr_files, after_files):
                # The files must be the same except for any header information:
                instr_data = read_mccode_dat(instr_file)
                after_data = read_mccode_dat(after_file)
                self.assertTrue(allclose(instr_data.data, after_data.data))

    @compiled_test
    def test_assemble_a3_rotation(self):
        from mccode_antlr.assembler import Assembler
        a = Assembler('test_a3_angle', flavor=Flavor.MCSTAS)
        a.parameter('phase/"degree" = 0')
        a.parameter('a3/"degree" = 0')
        a.component('origin', 'Progress_bar')
        a.component('source', 'ESS_butterfly', at=[(0, 0, 0), 'origin'],
                    parameters={'sector': '"W"', 'beamline': 4, 'yheight': 0.03, 'cold_frac': 0.5,
                                'dist': 1, 'focus_xw': 0.01, 'focus_yh': 0.01, 'c_performance': 1.0,
                                't_performance': 1.0, 'Lmin': 1, 'Lmax': 2, 'tmax_multiplier': 1.5,
                                'n_pulses': 1, 'acc_power': 2.0})
        a.component('guide', 'Guide_gravity', at=[(0, 0, 1), 'origin'],
                    parameters={'w1': 0.01, 'w2': 0.05, 'h1': 0.01, 'h2': 0.05, 'l': 8.0, 'm': 3.5, 'G':-9.82})
        a.component('guide_end', 'Arm', at=[(0, 0, 8.0), 'guide'])
        a.component('chopper', 'DiskChopper', at=([0, 0, 0.01], 'guide_end'),
                    parameters={'radius':0.35, 'nu': 14, 'phase': 'phase', 'theta_0': 115.0})
        a.component('rotate', 'Arm', at=([0, 0, 0], 'chopper'), rotate=([0, 'a3', 0], 'chopper'))
        a.component('aperture', 'Slit', at=([0, 0, 1], 'rotate'),
                    parameters={'xwidth': 0.05, 'yheight': 0.05})
        a.component('sample', 'Incoherent', at=([0, 0, 1], 'aperture'),
                    parameters={'radius': 0.005, 'yheight': 0.02, 'thickness': 0.001, 'focus_ah': 2.0,
                                'focus_aw': 2.0, 'target_x': 1.0, 'target_y': 0.0, 'target_z': 0.0,
                                'Etrans': 0.0, 'deltaE': 0.1})
        instr = a.instrument
        try:
            compile_and_run(instr, '-n 1000 a3=10', run=True)
        except RuntimeError as e:
            logger.error(f'Failed to compile instrument: {e}')
            self.fail(f'Failed to compile instrument {e}')