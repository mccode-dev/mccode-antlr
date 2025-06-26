import unittest
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler


def curved_guide_inserter():
    from numpy import ones, hstack
    small_distance = 1e-05  # m, Small value to separate components
    curved_guide_lengths = 0.5 * ones(3)  # 36 segments approximating the curve, but two are broken into two guides
    curved_guide_angles = 0.01886551 * ones(3)  # this is 'benderAngle' from the original file
    curved_guide_x_translations = 7.57345916228e-10 * ones(3)
    curved_guide_x_translations[0] = 0.
    # Each guide segment was either 'u', 'u + 6e-5 + [previous length]', or '0 + [previous length]' translated along z
    curved_guide_z_translations = hstack((small_distance, 7 * small_distance + curved_guide_lengths[:-1]))

    def add_curved_guide_piece(assembler, number):
        # guide pieces are translated along beam path, and moved sideways due to curvature
        at = curved_guide_x_translations[number], 0, curved_guide_z_translations[number]
        # rotated around the vertical axis
        rot = 0, curved_guide_angles[number], 0
        rel = 'end_element6' if number < 1 else f'curved_guide_segment_{number - 1:02d}'
        seg_name = f'curved_guide_segment_{number:02d}'
        seg = assembler.component(seg_name, 'Guide_gravity', at=(at, rel), rotate=(rot, rel))
        seg.set_parameters(w1=0.029534, h1=0.047514, w2=0.029534, h2=0.047514, l=curved_guide_lengths[number], R0=0.99,
                           Qc=0.0217, alpha=3.1, W=0.003, mleft=3.0, mright=3.5, mtop=2.5, mbottom=2.5, G=-9.82)
        end_name = f'{seg_name}_end'
        assembler.component(end_name, 'Arm', at=((0, 0, curved_guide_lengths[number] + 1e-6), seg_name))
        return seg_name, end_name

    return add_curved_guide_piece


def add_elliptic_guide(assembler, name, at=None, relative=None, **kwargs):
    if at is None:
        at = [0, 0, 1e-5]
    guide = assembler.component(name, 'Elliptic_guide_gravity', at=(at, relative))
    guide.set_parameters(dimensionsAt="\"mid\"", R0=0.99, Qc=0.0217, alpha=3.1, W=0.003, **kwargs)
    return guide


def declare_nboa_guide_parameters(assembler):
    def declare_line(name, vec):
        initializer = '{' + ','.join(f'{x}' for x in vec) + '}'
        return f'double {name}[] = {initializer};'

    # Neutron Beam Optical Assembly (NBOA) in-monolith guide:
    nboa = dict()
    nboa['nboa_lens'] = [
        0.48844444, 0.48844444, 0.48844444, 0.48844444, 0.48844444, 0.48844444, 0.48844444, 0.06121889, 0.02349,
        0.40373556, 0.07626444, 0.015, 0.39671
    ]
    nboa['nboa_vert'] = [3.5, 3.5, 3.0, 3.0, 2.5, 2.5, 2.5, 2.5, 0.0, 2.0, 2.0, 0.0, 2.0]
    nboa['nboa_horz'] = [3.0, 3.0, 2.5, 2.5, 2.5, 2.0, 1.5, 1.5, 0.0, 1.5, 1.5, 0.0, 1.5]

    assembler.declare('\n'.join([declare_line(n, v) for n, v in nboa.items()]), source=__file__)

    return nboa['nboa_lens']


def insert_truncated_bifrost_primary(b: Assembler):
    import numpy as np

    eps = 1e-05  # m, Small value to separate components

    el6_lens = declare_nboa_guide_parameters(b)

    # call-time defined instrument parameters
    parameters = [
        'int pulses = 1', 'power/"MW" = 2',
        'source_lambda_min/"angstrom" = 0.75', 'source_lambda_max/"angstrom" = 30',
    ]
    for parameter in parameters:
        b.parameter(parameter)

    # Start the actual instrument:
    b.component("Origin", "Progress_bar", at=[0, 0, 0])

    # Element 6 (NBOA) start position relative the source
    el6_s = np.array([0.01277, 0, 1.903398 - eps])
    # Element 6 (NBOA) end position relative its start -- it's length
    el6_d = np.array([0, 0, 4.39553 + 2 * eps])

    source_to_nboa_entrance = 1.903398
    nboa_entrance_width = 0.068797 + 2 * 0.01277
    nboa_entrance_height = 0.03472
    curved_guide_reflections_count = None
    b.component("ESS_source", "ESS_butterfly", at=[0, 0, 0], rotate=[0, 0, 0]) \
        .set_parameters(sector="\"W\"", beamline=4, yheight=0.03, cold_frac=0.5, dist=source_to_nboa_entrance,
                        focus_xw=nboa_entrance_width, focus_yh=nboa_entrance_height,
                        c_performance=1.0, t_performance=1.0, Lmin="source_lambda_min", Lmax="source_lambda_max",
                        tmax_multiplier=1.500000, n_pulses="pulses", acc_power="power",
                        # tfocus_dist="tf_d", tfocus_time="tf_t", tfocus_width="1.1*tf_w"
                        )

    b.component("GuideStart", "Arm", at=(list(el6_s), 'Origin'), rotate=([0, -0.56, 0], 'Origin'))

    # The NBOA is element6 -- its return value is not used and originally had the parameter l specified twice: l=4.39553
    add_elliptic_guide(b, "NBOA", relative='GuideStart',
                       xwidth=0.069634, yheight=0.04862, linxw=3.4578, loutxw=0.415155, linyh=1.36, loutyh=3.487681,
                       seglength="nboa_lens", mvaluesright="nboa_horz", mvaluesleft="nboa_horz",
                       mvaluestop="nboa_vert", mvaluesbottom="nboa_vert", nSegments=len(el6_lens),
                       # l="+".join([f"{x}" for x in el6_lens])  # Push the sum to C, to avoid rounding errors?
                       l=sum(el6_lens)
                       )

    b.component("end_element6", "Arm", at=(list(el6_d), "PREVIOUS"))
    b.component("end_element5", "Arm", at=([0, 0, 0.081707], "end_element6"))

    add_curved_guide_piece = curved_guide_inserter()
    guide_0_segment, guide_0_end = add_curved_guide_piece(b, 0)
    guide_1_segment, guide_1_end = add_curved_guide_piece(b, 1)

    split_at = b.component('split_at', 'Arm', at=([0, 0, 2 * eps], guide_1_end))

    sample_stack = b.component("sample_stack", "Arm", at=([0, 0, 0.58], split_at))

    return b, split_at, sample_stack


def make_truncated_bifrost():
    from mccode_antlr.assembler import Assembler
    bifrost = Assembler('BIFROST', flavor=Flavor.MCSTAS)
    bifrost, split_at, sample_stack = insert_truncated_bifrost_primary(bifrost)
    return bifrost.instrument


class SplitBifrostTestCase(unittest.TestCase):
    def setUp(self):
        self.bifrost = make_truncated_bifrost()

    def assertBothReferencesEqual(self, comp, ref):
        self.assertEqual(comp.at_relative[1], ref)
        self.assertEqual(comp.rotate_relative[1], ref)

    def _test_relative_references(self, instr):
        origin = instr.get_component('Origin')
        guide_start = instr.get_component('GuideStart')
        nboa = instr.get_component('NBOA')
        end_element_6 = instr.get_component('end_element6')
        guide0 = instr.get_component('curved_guide_segment_00')
        guide1 = instr.get_component('curved_guide_segment_01')
        self.assertBothReferencesEqual(guide_start, origin)
        self.assertBothReferencesEqual(nboa, guide_start)
        self.assertBothReferencesEqual(end_element_6, nboa)
        self.assertBothReferencesEqual(guide0, end_element_6)
        self.assertBothReferencesEqual(guide1, guide0)

    def test_pre(self):
        self._test_relative_references(self.bifrost)

    def test_split(self):
        before, after = self.bifrost.mcpl_split(self.bifrost.get_component('split_at'))
        self._test_relative_references(before)


class SplitHDF5BifrostTestCase(SplitBifrostTestCase):
    def setUp(self):
        from pathlib import Path
        from tempfile import mkdtemp
        from importlib.util import find_spec
        if not find_spec('h5py'):
            self.skipTest('h5py not found -- skipping HDF5 tests')
        else:
            from mccode_antlr.io import save_hdf5, load_hdf5
            self.td = Path(mkdtemp())
            filepath = self.td.joinpath('bifrost.h5')
            save_hdf5(make_truncated_bifrost(), filepath)
            self.bifrost = load_hdf5(filepath)

    def test_load_parameters(self):
        from mccode_antlr.io import load_hdf5
        from mccode_antlr.common import InstrumentParameter
        parameters = load_hdf5(self.td.joinpath('bifrost.h5'), 'parameters')
        self.assertTrue(isinstance(parameters, tuple))
        self.assertTrue(all(isinstance(p, InstrumentParameter) for p in parameters))

        expected = [InstrumentParameter.parse(s) for s in (
            'int pulses = 1', 'power/"MW" = 2', 'source_lambda_min/"angstrom" = 0.75',
            'source_lambda_max/"angstrom" = 30',)]
        self.assertEqual(len(parameters), len(expected))
        self.assertTrue(all(x in expected for x in parameters))
        self.assertTrue(all(x in parameters for x in expected))


    def tearDown(self):
        from shutil import rmtree
        rmtree(self.td)


if __name__ == '__main__':
    unittest.main()
