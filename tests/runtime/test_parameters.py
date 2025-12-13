from mccode_antlr.test import compiled_test
from mccode_antlr.utils import compile_and_run

@compiled_test
def test_parameters():
    """Ensure that instrument parameters are available for 'when' statements, e.g., in the raytrace section"""
    from mccode_antlr.loader.loader import parse_mcstas_instr
    from textwrap import dedent
    instr = parse_mcstas_instr(dedent("""\
        define instrument test_parameters(int boolean_value=1)
        declare %{int count;%}
        initialize %{count = -1;%}
        trace
        component o = Arm() at (0,0,0) absolute extend %{++count;%}
        component a = Arm() when (count%4==0) at (0,0,0) absolute 
                      extend %{printf("a=%d\\n", count); SCATTER; %}
        component b = Arm() when (count%2==0) at (0,0,0) absolute 
                      extend %{printf("b=%d\\n", count);%}
        component c = Arm() when (boolean_value && count%2) at (0,0,0) absolute
                      extend %{printf("c=%d\\n", count);%}
        end 
    """))
    n_max = 5
    for boolean_value in [0, 1]:
        results, data = compile_and_run(instr, f"-n {n_max} boolean_value={boolean_value}")
        lines = results.decode('utf-8').splitlines()
        print(lines)
        expected = []
        for i in range(n_max):
            if i % 4 == 0:
                expected.append(f'a={i}')
            if i % 2 == 0:
                expected.append(f'b={i}')
            if boolean_value and i % 2:
                expected.append(f'c={i}')

        for ex, ln in zip(expected, lines):
            assert ex == ln


@compiled_test
def test_declared_component_setting_parameter():
    """Ensure that instrument parameters are available for 'when' statements, e.g., in the raytrace section"""
    from mccode_antlr.loader.loader import parse_mcstas_instr
    from textwrap import dedent
    instr_source = dedent("""\
        define instrument test_declared_component_setting_parameter(dummy=1)
        declare %{
        double ex;
        double thickness;
        int values[1];
        %}
        initialize %{
        ex=0.3;
        thickness=110.0;
        values[0] = -909;
        %}
        trace
        component o = Arm() at (0,0,0) absolute
        component a = Arm() at (ex,0,0) absolute extend %{ printf("ex=%0.2f\\n", ex); %}
        component b = Progress_bar(percent=thickness) at (0,0,0) absolute
                      extend %{ printf("thickness=%0.2f\\n", thickness);%}
        component c = Al_window(thickness=-ex / values[0]) at (0,0,0) absolute
                      extend %{ printf("thickness=%0.5f\\n", thickness);%}
        end 
    """)
    instr = parse_mcstas_instr(instr_source)
    n_max = 2
    results, data = compile_and_run(instr, f"-n {n_max} dummy=2")
    lines = results.decode('utf-8').splitlines()
    print(lines)
    expected = []
    for i in range(n_max):
        expected.append(f'ex=0.30')
        expected.append(f'thickness=110.00')
        expected.append(f'thickness=0.00033')

    for ex, ln in zip(expected, lines[1:]):
        assert ex == ln