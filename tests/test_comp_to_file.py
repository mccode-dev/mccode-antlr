"""Comp.to_string writes a definition that reads back as the same component (#391)."""
from mccode_antlr.comp import Comp
from mccode_antlr.common import DataType

SOURCE = '''DEFINE COMPONENT Everything
DEFINITION PARAMETERS (int n=3)
SETTING PARAMETERS (a, b=1e-4, int c=2, string s="x", string none=0, char *cs=NULL,
  vector v=NULL, vector w={1, 2, 3}, vector u=nm, double *d, int *i={1, 2}, int *j,
  symbol big=FLT_MAX)
OUTPUT PARAMETERS (o)
METADATA "text/plain" note %{
a note
%}
DEPENDENCY "-lm"
NOACC
SHARE %{
double helper(double x) { return x; }
%}
USERVARS %{ int seen; %}
DECLARE %{
double total;
%}
INITIALIZE %{
total = 0;
%}
TRACE %{
total += helper(a);
%}
SAVE %{
%}
FINALLY %{
total = 0;
%}
MCDISPLAY %{
line(0,0,0, 1,0,0);
%}
END
'''


def _read(source):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')  # `symbol` is archaic, and says so
        return Comp.from_source(None, None, source)


def _parameters(comp):
    return [(p.name, str(p.value), p.value.data_type, p.value.shape_type, p.value.object_type)
            for p in comp.define + comp.setting + comp.output]


def test_a_written_component_reads_back_the_same():
    original = _read(SOURCE)
    written = original.to_string()
    back = _read(written)
    assert _parameters(back) == _parameters(original)
    assert back.dependency == original.dependency == '-lm'
    assert back.acc is original.acc is False
    assert [(m.name, m.mimetype, m.value) for m in back.metadata] == \
        [(m.name, m.mimetype, m.value) for m in original.metadata]
    for block in ('share', 'user', 'declare', 'initialize', 'trace', 'save', 'final', 'display'):
        # an inline `%{ ... %}` gains its own lines once, and keeps them thereafter
        assert [str(r).strip() for r in getattr(back, block)] == \
            [str(r).strip() for r in getattr(original, block)]
    assert back.to_string() == written


def test_vector_and_array_parameters_keep_their_type_and_default():
    written = _read(SOURCE).to_string()
    for text in ('vector v=NULL', 'vector w={1,2,3}', 'vector u=nm', 'vector d,',
                 'int *i={1,2}', 'int *j,', 'symbol big=FLT_MAX'):
        assert text in written
    i = next(p for p in _read(written).setting if p.name == 'i')
    assert i.value.data_type == DataType.int and i.value.is_vector
