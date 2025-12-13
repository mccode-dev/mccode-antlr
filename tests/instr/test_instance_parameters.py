from unittest import TestCase
from loguru import logger


class TestInstrInstanceParameters(TestCase):
    def test_assemble_identifier_instance_parameter(self):
        from mccode_antlr.utils import make_assembler
        assembler = make_assembler('fake_bifrost')

        parameters = [
            'ps1speed/"Hz" = 196', 'ps2speed/"Hz" = 196',
            'fo1speed/"Hz" = 14', 'fo2speed/"Hz" = 14',
            'bw1speed/"Hz" = 14', 'bw2speed/"Hz" = -14',
            'ps1phase/"Hz" = 0', 'ps2phase/"Hz" = 0',
            'fo1phase/"Hz" = 0', 'fo2phase/"Hz" = 0',
            'bw1phase/"Hz" = 0', 'bw2phase/"Hz" = 0',
            'blade0l/"m" = -0.05', 'blade0r/"m" = 0.05',
            'blade1l/"m" = -0.05', 'blade1r/"m" = 0.05',
            'blade2l/"m" = -0.05', 'blade2r/"m" = 0.05',
            'blade3l/"m" = -0.05', 'blade3r/"m" = 0.05',
            'int pulses = 1', 'power/"MW" = 2',
            'source_lambda_min/"angstrom" = 0.75', 'source_lambda_max/"angstrom" = 30',
        ]
        assembler.parameters(*parameters)

        # Mix of initialization temporary variables and calculated instrument parameters.
        pulse_length = 2.86E-3
        assembler.declare(f"""
         double lambda_0;
         double lambda_1;
         double tf_d=1;
         double tf_t={pulse_length / 2};
         double tf_w={pulse_length};
         double tf_tau={1 / 14.0};
         double ps_disk_open_angle=170.0;
         double ps_distance={4.41 + 0.032 + 2.0 - 0.1};
         double bw_disk_open_angle=161.0;
         double bw_distance=78.0;
         """)

        # Chopper-based wavelength calculations can only be done at runtime since they depend on instrument parameters
        new_chopper_calculations = """
         chopper_parameters * pars = calloc(6, sizeof(chopper_parameters));
         pars[0].speed = ps1speed; // Pulse shaping disk 1
         pars[0].phase = ps1phase;
         pars[0].angle = 170.0;
         pars[0].path = ps_distance;
         pars[1].speed = ps2speed; // Pulse shaping disk 2
         pars[1].phase = ps2phase;
         pars[1].angle = pars[0].angle;
         pars[1].path = pars[0].path + 0.02;
         pars[2].speed = fo1speed; // Frame overlap 1
         pars[2].phase = fo1phase;
         pars[2].angle = 38.26;
         pars[2].path = 8.530;
         pars[3].speed = fo2speed; // Frame overlap 2
         pars[3].phase = fo2phase;
         pars[3].angle = 52.01;
         pars[3].path = 14.973;
         pars[4].speed = bw1speed; // Bandwidth disk 1
         pars[4].phase = bw1phase;
         pars[4].angle = 161.0;
         pars[4].path = bw_distance;
         pars[5].speed = bw2speed; // Bandwidth disk 2
         pars[5].phase = bw2phase;
         pars[5].angle = pars[4].angle;
         pars[5].path = pars[4].path + 0.02;

         lambda_0 = source_lambda_min;
         lambda_1 = source_lambda_max;
         double pulse_delay = 2.0e-4; // time to peak brightness after proton pulse T0
         double pulse_width = 2.86e-3; // duration of high flux plateau
         double latest = pulse_delay + pulse_width + 2e-3; // extra for good measure?
         unsigned windows = chopper_wavelength_limits(&source_lambda_min, &source_lambda_max, 6, pars, lambda_0, lambda_1, latest);

         // free the memory used by pars
         if (pars) free(pars);

         if (windows == 0) {
           printf("Chopper train will not pass wavelengths between %f and %f angstrom!\\n", lambda_0, lambda_1);
           printf("Examine the provided chopper speeds and phases.\\n");
         }
         if (windows > 1) {
           printf("Chopper train will pass %u wavelength ranges between %f and %f angstrom\\n", windows, lambda_0, lambda_1);
           printf("but only their envelope between %f and %f angstrom is considered!\\n", source_lambda_min, source_lambda_max);   
         }
         printf("Using source lambda limits %f to %f\\n", source_lambda_min, source_lambda_max);

         // Now calculate the time-focusing window on the first chopper given the wavelength band:
         // ...

         """
        assembler.initialize(new_chopper_calculations)

        # Start the actual instrument:
        assembler.component("Origin", "Progress_bar", at=[0, 0, 0])

        # Elliptic guide gravity initialization and declaration
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

        el6_lens = nboa['nboa_lens']

        guide = assembler.component("NBOA", 'Elliptic_guide_gravity', at=([0, 0, 1e-5], "PREVIOUS"))
        # make sure that array-valued parameters can be set:
        guide.set_parameters(dimensionsAt="\"mid\"", R0=0.99, Qc=0.0217, alpha=3.1, W=0.003, xwidth=0.069634,
                             yheight=0.04862, linxw=3.4578, loutxw=0.415155, linyh=1.36, loutyh=3.487681,
                             seglength="nboa_lens", mvaluesright="nboa_horz", mvaluesleft="nboa_horz",
                             mvaluestop="nboa_vert", mvaluesbottom="nboa_vert", nSegments=len(el6_lens),
                             l=sum(el6_lens))

        # Bandwidth chopper
        bw_upstream_gap = 0.1
        bwc1 = assembler.component("BWC1", "DiskChopper", at=([0, 0, bw_upstream_gap], "PREVIOUS"))
        bwc1.set_parameters(theta_0="bw_disk_open_angle", radius='1+2+3+4', nslit='(2+4)/(1+2)', yheight=0.1,
                            nu="bw1speed", phase="bw1phase/2")

        for par in ('theta_0', 'nslit', 'nu', 'phase'):
            self.assertFalse(bwc1.get_parameter(par).value.is_constant)
        for par in ('radius', 'yheight'):
            self.assertTrue(bwc1.get_parameter(par).value.is_constant)

        # nslit is not a constant parameter because the expression parsing does not simplify grouped expressions
        nslit = bwc1.get_parameter('nslit').value.simplify()
        # But explicitly simplifying the expression is possible (in this simple case) and yields a constant value
        self.assertTrue(nslit.simplify().is_constant)

        phase = bwc1.get_parameter('phase').value  # == bw1phase / 2
        # In contrast, phase is Expr(BinaryOp('/', Expr.id('bw1phase'), Expr.int(2))) which can't be simplified
        self.assertFalse(phase.simplify().is_constant)

        # But we can attempt to parse the declarations and instantiation blocks from the instrument
        from mccode_antlr.translators.c_listener import extract_c_declared_expressions, evaluate_c_defined_expressions
        # Here variables _is_ and _must be_ dict[str, Expr]
        variables = {x.name: x.value for x in assembler.instrument.parameters}
        for dec in assembler.instrument.declare:
            # This produces dict[CDeclarator, Expr]
            decs_expr = extract_c_declared_expressions(dec.source)
            # So extract just the CDeclarator's name
            variables.update({key.name: val for key, val in decs_expr.items()})

        # defined as
        # TODO this does not work because the simple "C"-style expression parser doesn't know about pointers
        try:
            for init in assembler.instrument.initialize:
                variables = evaluate_c_defined_expressions(variables, init.source)
        except AttributeError:
            logger.warning('Evaluating INITIALIZE section failed; see preceding errors for hints for why. '
                           'This is not a test failure condition (for now). Continuing')

        evaluated_phase = phase.evaluate(variables)
        self.assertTrue(evaluated_phase.is_constant)

        theta_0 = bwc1.get_parameter('theta_0').value
        self.assertTrue(theta_0.evaluate(variables).is_constant)

        # We want to know whether an expression involves any instrument parameters
        # -- which phase and nu do, but others do not:
        for x in ('phase', 'nu'):
            par = bwc1.get_parameter(x).value
            dep = any(par.depends_on(inst_par.name) for inst_par in assembler.instrument.parameters)
            self.assertTrue(dep)
        for x in ('theta_0', 'radius', 'nslit', 'yheight'):
            par = bwc1.get_parameter(x).value
            self.assertFalse(any(par.depends_on(inst_par.name) for inst_par in assembler.instrument.parameters))
