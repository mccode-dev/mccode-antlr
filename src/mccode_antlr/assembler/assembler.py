from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Union
from ..common import Expr, InstrumentParameter
from ..instr import Instr, Instance
from ..reader import Reader, Registry
from loguru import logger
from mccode_antlr import Flavor
from mccode_antlr.instr.orientation import Vector, Angles

class Assembler:
    """Interactive instrument assembly"""

    def __init__(self, name: str, registries: list[Registry] = None, flavor: Flavor | None = None,
                 parent: Assembler | None = None):
        from ..reader.registry import ordered_registries, ensure_registries
        self.parent = parent
        if parent is not None:
            if registries is not None or flavor is not None:
                raise ValueError('A child Assembler shares its parent reader: do not provide registries or flavor')
            self.reader = parent.reader
            self.instrument = Instr(name, source='interactive')
            self.instrument.registries = self.reader.registries
            return
        if flavor is not None:
            if isinstance(flavor, str):
                raise ValueError('flavor must be a Flavor Enum or None')
            registries = ensure_registries(flavor, registries)
        if registries is not None:
            registries = list(ordered_registries(registries))
        self.instrument = Instr(name, source='interactive')
        self.reader = Reader(registries=registries) if registries is not None else Reader()
        self.instrument.registries = self.reader.registries

    @contextmanager
    def included(self, name: str):
        """Build a child instrument inline; on clean exit it is merged into this
        instrument with provenance tags and stored in `instrument.included`.

        >>> with assembler.included('guide_section') as sub:
        ...     sub.component('g1', 'Arm', at=((0, 0, 1), 'origin'))

        The yielded object is a full Assembler sharing this one's reader, so
        every method (component, declare, parameter, nested included, ...) works.
        If the body raises, nothing is merged.
        """
        sub = Assembler(name, parent=self)
        yield sub
        self.instrument.include(sub.instrument)

    def include(self, instr: Instr | str | Path) -> Instr:
        """Merge an instrument (an Instr, or a name/path resolvable by this
        assembler's reader) into this one, with provenance tags.

        The passed Instr is absorbed and mutated: its instances are tagged and
        its REMOVABLE instances dropped, exactly as a TRACE %include would.
        """
        if not isinstance(instr, Instr):
            instr = self.reader.get_instrument(instr)
        else:
            # registry merge lives here, not in Instr.include, because
            # loader.parse_mccode_instr concatenates registries after parsing
            # and would duplicate them if Instr.include also merged
            for reg in instr.registries:
                if all(r.name != reg.name for r in self.instrument.registries):
                    self.instrument.registries += (reg,)
        self.instrument.include(instr)
        return instr

    def _lookup_component(self, name: str) -> Instance:
        scope = self
        while scope is not None:
            try:
                return scope.instrument.get_component(name)
            except (RuntimeError, IndexError):  # IndexError: 'PREVIOUS' on an empty child
                scope = scope.parent
        raise RuntimeError(f'No component instance named {name!r} in this assembler or its parent(s)')

    def _check_expr(self, expr):
        if not isinstance(expr, Expr):
            expr = Expr.best(expr)
        names = []
        scope = self
        while scope is not None:
            names.extend(x.name for x in scope.instrument.parameters)
            scope = scope.parent
        expr.verify_parameters(names)
        return expr

    @property
    def name(self):
        return self.instrument.name

    def _handle_at_rotate(self, a=None) -> tuple[tuple[Expr, Expr, Expr], Union[Instance,  None]]:
        if a is None:
            return (Expr.float(0), Expr.float(0), Expr.float(0)), None
        if hasattr(a, '__len__') and len(a) == 3:
            a = a, 'ABSOLUTE'
        if not hasattr(a, '__len__') or len(a) != 2:
            raise RuntimeError('Require two-tuple of three values and a reference')
        v, ref = a
        if ref is not None and not isinstance(ref, Instance):
            if 'absolute' == ref.lower():
                ref = None
            elif isinstance(ref, str):
                # Get the component instance by name, searching parent assemblers too
                ref = self._lookup_component(ref)
            else:
                raise RuntimeError(f'No logic pathway for instance reference {ref}')
        if not hasattr(v, '__len__') or len(v) != 3:
            raise RuntimeError('Position/orientation must have three elements')
        v = tuple(self._check_expr(x) for x in v)
        return (v[0], v[1], v[2]), ref

    def _handle_at(self, a=None) -> tuple[Vector, Union[Instance, None]]:
        at_tuple, ref = self._handle_at_rotate(a)
        return Vector(*at_tuple), ref

    def _handle_rotate(self, a=None, at_ref=None) -> tuple[Angles, Union[Instance, None]]:
        rot_tuple, ref = self._handle_at_rotate(a)
        # Only inherit at_ref when ROTATED is fully omitted (a is None).
        # A bare 3-tuple and an explicit 'ABSOLUTE' both mean the global frame (ref=None).
        return Angles(*rot_tuple), at_ref if a is None else ref

    def component(self, name: str, type_name: str, at=None, rotate=None, parameters=None, **kwargs):
        """Add a component to the underlying Instr.

        Parameters
        ----------
        name : str
            The name of the component instance.
        type_name : str
            The name of the component type.
        at : tuple, optional
            The position and orientation of the component instance.
            If not provided, the component will be placed at the origin.
        rotate : tuple, optional
            The rotation of the component instance.
            If not provided, the component will be rotated to match the at argument.
        parameters : dict, optional
            A dictionary of parameter names and values to set for the component instance.
        kwargs : dict, optional
            Properties for the constructed component Instance object. Useful keyword values include
            `when` and `group`.

        Note
        ----
        See `Assembler._handle_at` and `Assembler._handle_rotate` for details on the at and rotate arguments.
        """
        comp_type = self.reader.get_component(type_name)
        if type_name != comp_type.name:
            raise RuntimeError(f"Component resolution failed for {type_name}, found {comp_type.name} instead")
        at, ref = self._handle_at(at)
        instance = Instance(name, comp_type,
                            at_relative=(at, ref), rotate_relative=self._handle_rotate(rotate, ref),
                            **kwargs)
        self.instrument.add_component(instance)
        if isinstance(parameters, dict):
            instance.set_parameters(**parameters)
        return instance

    def parameter(self, par, ignore_repeated=False):
        """Add a parameter to the underlying Instr.

        Note
        ----
        The ignore_repeated keyword argument can be set to True in order to merely ensure that a parameter exists.
        Otherwise, repeatedly specifying the same parameter will raise a RuntimeError.
        """
        if isinstance(par, str):
            par = InstrumentParameter.parse(par)
        if not isinstance(par, InstrumentParameter):
            logger.warning(f'Unhandled parameter {par}')
        self.instrument.add_parameter(par, ignore_repeated=ignore_repeated)

    def parameters(self, *pars, **pairs):
        for par in list(pars):
            if isinstance(par, str):
                par = InstrumentParameter.parse(par)
            if not isinstance(par, InstrumentParameter):
                logger.warning(f'Unhandled parameter(s) {par}')
            self.instrument.add_parameter(par)

        for name, value in pairs.items():
            if not isinstance(value, InstrumentParameter):
                if isinstance(value, dict) and 'unit' in value and 'value' in value:
                    value, unit = value['value'], value['unit']
                elif isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[1], str):
                    value, unit = value
                else:
                    unit = ''
                value = InstrumentParameter(name, unit, value if isinstance(value, Expr) else Expr.best(value))
            self.instrument.add_parameter(value)

    def declare(self, string, source=None, line=-1):
        return _rawc_call(self.instrument.DECLARE, string, source or f'{self.name}.instr', line)

    def declare_array(self, dtype: str, name: str, init: list, source=None, line=-1):
        return self.declare(f'{dtype} {name}[] = {{{",".join(str(x) for x in init)}}};', source=source, line=line)

    def user_vars(self, string, source=None, line=-1):
        return _rawc_call(self.instrument.USERVARS, string, source or f'{self.name}.instr', line)

    def ensure_user_var(self, string, source=None, line=-1):
        # tying the Assembler to work with C might not be great
        from mccode_antlr.translators.c_listener import extract_c_declared_variables as parse
        variables = parse(string)
        if len(variables) == 0:
            raise ValueError(f'The provided input {string} does not specify a C parameter declaration.')
        if len(variables) != 1:
            print(f'The provided input {string} specifies {len(variables)} C parameter declarations, using only the first')
        decl = variables[0]
        name = decl.name
        dtype = decl.dtype
        for user_vars in self.instrument.user:
            uv_variables = parse(user_vars.source)
            if any(x.dtype == dtype and x.name == name for x in uv_variables):
                return
            if any(x.name == name for x in uv_variables):
                print(f'A USERVARS variable with name {name} but type different than {dtype} has already been defined.')
                return
        return self.user_vars(string, source=source, line=line)

    def initialize(self, string, source=None, line=-1):
        return _rawc_call(self.instrument.INITIALIZE, string, source or f'{self.name}.instr', line)

    def save(self, string, source=None, line=-1):
        return _rawc_call(self.instrument.SAVE, string, source or f'{self.name}.instr', line)

    def final(self, string, source=None, line=-1):
        return _rawc_call(self.instrument.FINALLY, string, source or f'{self.name}.instr', line)

    def metadata(self, name: str, mimetype: str, value: str, source=None):
        from mccode_antlr.common.metadata import MetaData
        self.instrument.add_metadata(MetaData.from_instrument_tokens(source, mimetype, name, value))


def _rawc_call(method, string: str, source: str | None = None, line: int = -1):
    from mccode_antlr.common import RawC
    return method(RawC(source, line, string))


INTENDED_USAGE = """
bifrost = Assembler('bifrost', registries=[local_bifrost_components], flavor=mcstas_antlr.Flavor.MCSTAS)
bifrost.parameters(par1=5.11, par2=('m', 100), par3={'value': 3.14159, 'unit': 'radian'})
...
bifrost.component('source, 'ESS_BUTTERFLY').set_parameters(...)
...
"""