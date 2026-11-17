import pytest


def _assembler():
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    return Assembler('test', flavor=Flavor.MCSTAS)


def test_ensure_user_var_declares_once():
    a = _assembler()
    a.ensure_user_var('int TUBE;')
    a.ensure_user_var('int TUBE;')
    assert sum(block.source.count('TUBE') for block in a.instrument.user) == 1


def test_ensure_user_var_type_conflict_raises():
    """particle_setvar_void copies sizeof(the declared type), so a second type is an error."""
    a = _assembler()
    a.ensure_user_var('int event_charge_left;')
    with pytest.raises(ValueError, match='already declared as int'):
        a.ensure_user_var('double event_charge_left;')
