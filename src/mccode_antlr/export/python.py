from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

from mccode_antlr.instr import Instr
from mccode_antlr.reader import (
    LocalRegistry, RemoteRegistry, ModuleRemoteRegistry, GitHubRegistry, InMemoryRegistry
)


def _infer_flavor(instr: Instr) -> str:
    names = {reg.name.lower() for reg in instr.registries}
    return 'MCXTRACE' if 'mcxtrace' in names else 'MCSTAS'


def _safe_name(name: str, used: set[str]) -> str:
    import re
    ident = re.sub(r'[^0-9a-zA-Z_]', '_', name)
    if not ident or ident[0].isdigit():
        ident = f'comp_{ident}'
    ident = f'comp_{ident}'
    candidate = ident
    i = 1
    while candidate in used:
        i += 1
        candidate = f'{ident}_{i}'
    used.add(candidate)
    return candidate


def _expr_as_python_literal(expr) -> str:
    if expr.is_vector and expr.vector_known:
        return f"Expr.array({expr.value!r})"
    if expr.has_value:
        return repr(expr.value)
    return repr(str(expr))


def _emit_vector_reference(vr, instances: dict[str, str]) -> str:
    vec, ref = vr
    values = ', '.join(_expr_as_python_literal(x) for x in vec)
    vec_repr = f'[{values}]'
    if ref is None:
        return f'({vec_repr}, "ABSOLUTE")'
    return f'({vec_repr}, {instances.get(ref.name, repr(ref.name))})'


def _ref_name(ref) -> str | None:
    return None if ref is None else ref.name


def _expr_text(expr) -> str:
    return str(expr)


def _expr_num(expr):
    if not expr.has_value:
        return None
    value = expr.value
    return value if isinstance(value, (int, float)) else None


def _instance_signature(inst) -> tuple:
    return (
        inst.type.name,
        tuple((p.name, _expr_text(p.value)) for p in inst.parameters),
        _ref_name(inst.at_relative[1]),
        tuple(_expr_text(x) for x in inst.rotate_relative[0]),
        _ref_name(inst.rotate_relative[1]),
        None if inst.when is None else _expr_text(inst.when),
        inst.group,
        inst.removable,
        inst.cpu,
        None if inst.split is None else _expr_text(inst.split),
        tuple(ext.source for ext in inst.extend),
        tuple((j.target, j.relative_target, j.iterate, _expr_text(j.condition), j.absolute_target) for j in inst.jump),
        tuple((md.source.type_name, md.source.name, md.name, md.mimetype, md.value) for md in inst.metadata),
    )


def _name_series(instance_names: list[str]) -> tuple[str, int] | None:
    import re
    first = re.match(r'^(.*?)(\d+)$', instance_names[0])
    if first is None:
        return None
    prefix = first.group(1)
    start = int(first.group(2))
    width = len(first.group(2))
    for i, name in enumerate(instance_names[1:], start=1):
        m = re.match(r'^(.*?)(\d+)$', name)
        if m is None or m.group(1) != prefix or len(m.group(2)) != width or int(m.group(2)) != start + i:
            return None
    return prefix, start


def _vector_axis_progression(vectors) -> tuple[int, int | float, int | float] | None:
    values = [[_expr_num(x) for x in vec] for vec in vectors]
    if any(any(v is None for v in row) for row in values):
        return None
    varying_axes = []
    axis_data = None
    for axis in range(3):
        seq = [row[axis] for row in values]
        delta = seq[1] - seq[0]
        if any((seq[i] - seq[i - 1]) != delta for i in range(2, len(seq))):
            return None
        if delta != 0:
            varying_axes.append(axis)
            axis_data = (axis, seq[0], delta)
    if len(varying_axes) != 1:
        return None
    return axis_data


@dataclass
class _LoopGroup:
    mode: str
    start: int
    end: int
    prefix: str
    start_index: int
    at_axis: int | None = None
    at_base: int | float | None = None
    at_delta: int | float | None = None


def _find_loop_groups(components: tuple) -> list[_LoopGroup]:
    def static_signature(inst):
        return (
            inst.type.name,
            tuple((p.name, _expr_text(p.value)) for p in inst.parameters),
            None if inst.when is None else _expr_text(inst.when),
            inst.group,
            inst.removable,
            inst.cpu,
            None if inst.split is None else _expr_text(inst.split),
            tuple(ext.source for ext in inst.extend),
            tuple((j.target, j.relative_target, j.iterate, _expr_text(j.condition), j.absolute_target) for j in inst.jump),
            tuple((md.source.type_name, md.source.name, md.name, md.mimetype, md.value) for md in inst.metadata),
        )

    def vector_text(v):
        return tuple(_expr_text(x) for x in v)

    def previous_chain_candidate(chunk, start, end, series):
        if len(chunk) < 3:
            return None
        signatures = [static_signature(inst) for inst in chunk]
        if not all(sig == signatures[0] for sig in signatures):
            return None
        at_delta = vector_text(chunk[1].at_relative[0])
        rotate_delta = vector_text(chunk[1].rotate_relative[0])
        for k in range(1, len(chunk)):
            prev = chunk[k - 1]
            curr = chunk[k]
            if _ref_name(curr.at_relative[1]) != prev.name:
                return None
            if _ref_name(curr.rotate_relative[1]) != prev.name:
                return None
            if vector_text(curr.at_relative[0]) != at_delta:
                return None
            if vector_text(curr.rotate_relative[0]) != rotate_delta:
                return None
        return _LoopGroup(mode='previous_chain', start=start, end=end,
                          prefix=series[0], start_index=series[1])

    def absolute_candidate(chunk, start, end, series):
        signatures = [_instance_signature(inst) for inst in chunk]
        if not all(sig == signatures[0] for sig in signatures):
            return None
        names = [inst.name for inst in chunk]
        at_ref = _ref_name(chunk[0].at_relative[1])
        if at_ref is not None and at_ref in names:
            return None
        vectors = [inst.at_relative[0] for inst in chunk]
        axis_prog = _vector_axis_progression(vectors)
        if axis_prog is None:
            return None
        axis, base, delta = axis_prog
        return _LoopGroup(mode='absolute_axis', start=start, end=end, prefix=series[0], start_index=series[1],
                          at_axis=axis, at_base=base, at_delta=delta)

    groups: list[_LoopGroup] = []
    i = 0
    while i < len(components):
        best: _LoopGroup | None = None
        for j in range(i + 3, len(components) + 1):
            chunk = components[i:j]
            names = [inst.name for inst in chunk]
            series = _name_series(names)
            if series is None:
                break
            candidate = previous_chain_candidate(chunk, i, j, series)
            if candidate is None:
                candidate = absolute_candidate(chunk, i, j, series)
            if candidate is not None:
                best = candidate
        if best is not None:
            groups.append(best)
            i = best.end
        else:
            i += 1
    return groups


def _component_kwargs(inst, instance_names: dict[str, str], *, name_expr: str | None = None,
                      at_expr: str | None = None, rotate_expr: str | None = None) -> list[str]:
    kwargs = [
        f'name={name_expr if name_expr is not None else repr(inst.name)}',
        f'type_name={inst.type.name!r}',
        f'at={at_expr if at_expr is not None else _emit_vector_reference(inst.at_relative, instance_names)}',
        f'rotate={rotate_expr if rotate_expr is not None else _emit_vector_reference(inst.rotate_relative, instance_names)}',
    ]
    if inst.parameters:
        param_pairs = [f'{p.name!r}: {_expr_as_python_literal(p.value)}' for p in inst.parameters]
        kwargs.append(f'parameters={{{", ".join(param_pairs)}}}')
    if inst.when is not None:
        kwargs.append(f'when=Expr.parse({str(inst.when)!r})')
    if inst.group is not None:
        kwargs.append(f'group={inst.group!r}')
    if inst.removable:
        kwargs.append('removable=True')
    if inst.cpu:
        kwargs.append('cpu=True')
    if inst.split is not None:
        kwargs.append(f'split=Expr.parse({str(inst.split)!r})')
    return kwargs


def _emit_component_post(lines: list[str], inst, var_name: str, indent: str = '    '):
    if inst.extend:
        blocks = ', '.join(repr(ext.source) for ext in inst.extend)
        lines.append(f'{indent}{var_name}.EXTEND({blocks})')
    if inst.jump:
        jumps = []
        for jump in inst.jump:
            jumps.append(
                f'Jump(target={jump.target!r}, relative_target={jump.relative_target!r}, '
                f'iterate={jump.iterate!r}, condition=Expr.parse({str(jump.condition)!r}), '
                f'absolute_target={jump.absolute_target!r})'
            )
        lines.append(f'{indent}{var_name}.JUMP({", ".join(jumps)})')
    for md in inst.metadata:
        lines.append(
            f'{indent}{var_name}.add_metadata(MetaData('
            f'DataSource.from_type_name_and_name({md.source.type_name!r}, {md.source.name!r}), '
            f'{md.name!r}, {md.mimetype!r}, {md.value!r}))'
        )


def _emit_component(inst, var_name: str, instance_names: dict[str, str]) -> list[str]:
    lines = []
    kwargs = _component_kwargs(inst, instance_names)
    lines.append(f'    {var_name} = a.component({", ".join(kwargs)})')
    _emit_component_post(lines, inst, var_name, indent='    ')
    return lines


def _emit_loop_group(group: _LoopGroup, chunk, instance_names: dict[str, str]) -> list[str]:
    lines = []
    inst = chunk[0]
    n = group.end - group.start
    if group.mode == 'previous_chain':
        seed_kwargs = _component_kwargs(inst, instance_names)
        lines.append(f'    last = a.component({", ".join(seed_kwargs)})')
        _emit_component_post(lines, inst, 'last', indent='    ')

        delta_inst = chunk[1]
        at_delta = ', '.join(_expr_as_python_literal(x) for x in delta_inst.at_relative[0])
        rot_delta = ', '.join(_expr_as_python_literal(x) for x in delta_inst.rotate_relative[0])
        lines.append(f'    for i in range({n - 1}):')
        kwargs = _component_kwargs(
            delta_inst, instance_names,
            name_expr=f'f"{group.prefix}{{i + {group.start_index + 1}}}"',
            at_expr=f'([{at_delta}], last)',
            rotate_expr=f'([{rot_delta}], last)',
        )
        lines.append(f'        last = a.component({", ".join(kwargs)})')
        _emit_component_post(lines, delta_inst, 'last', indent='        ')
        return lines

    lines.append(f'    for i in range({n}):')
    at_values = [_expr_as_python_literal(x) for x in inst.at_relative[0]]
    at_values[group.at_axis] = f'({group.at_base!r} + i * {group.at_delta!r})'
    at_ref = inst.at_relative[1]
    if at_ref is None:
        at_ref_repr = '"ABSOLUTE"'
    else:
        at_ref_repr = instance_names.get(at_ref.name, repr(at_ref.name))
    at_repr = f'([{", ".join(at_values)}], {at_ref_repr})'
    rotate_repr = _emit_vector_reference(inst.rotate_relative, instance_names)
    kwargs = _component_kwargs(
        inst, instance_names,
        name_expr=f'f"{group.prefix}{{i + {group.start_index}}}"',
        at_expr=at_repr,
        rotate_expr=rotate_repr,
    )
    lines.append(f'        _loop_inst = a.component({", ".join(kwargs)})')
    _emit_component_post(lines, inst, '_loop_inst', indent='        ')
    return lines


def _handle_registry(reg) -> tuple[str|None, list[str]]:
    rep, lines = None, []
    if isinstance(reg, (LocalRegistry, GitHubRegistry, ModuleRemoteRegistry, RemoteRegistry)):
        rep = f'registry_from_specification("{reg.specification_string()}")'
    elif isinstance(reg, InMemoryRegistry):
        rep = f'InMemoryRegistry({reg.name!r}, priority={reg.priority!r})'
        lines.append('    # This may not work -- good luck!')
        for comp_name, source in reg.components.items():
            lines.append(f'    {name}.add({comp_name!r}, {source!r})')
    else:
        lines = [f'    # Unsupported registry type preserved as comment: {type(reg).__name__}({reg!r})',]
    return rep, lines


def instr_to_python(instr: Instr, optimize: bool = False) -> str:
    has_metadata = bool(instr.metadata) or any(inst.metadata for inst in instr.components)
    has_jump = any(inst.jump for inst in instr.components)
    has_expr_array = any(
        p.value.is_vector and p.value.vector_known
        for inst in instr.components for p in inst.parameters
    )
    has_expr_parse = any(
        (inst.when is not None or inst.split is not None or any(j.condition is not None for j in inst.jump))
        for inst in instr.components
    )

    lines = [
        'from __future__ import annotations',
        '',
        'from mccode_antlr import Flavor',
        'from mccode_antlr.assembler import Assembler',
    ]
    if instr.registries:
        lines.extend([
            'from mccode_antlr.reader import (',
            '    LocalRegistry, RemoteRegistry, ModuleRemoteRegistry, GitHubRegistry, InMemoryRegistry,',
            ')',
        ])
    if has_expr_array or has_expr_parse:
        lines.append('from mccode_antlr.common.expression import Expr')
    if has_jump:
        lines.append('from mccode_antlr.instr import Jump')
    if has_metadata:
        lines.append('from mccode_antlr.common import MetaData')
        lines.append('from mccode_antlr.common.metadata import DataSource')

    lines.append('from mccode_antlr.reader.registry import registry_from_specification')

    lines.extend(['', '', 'def build_instrument():'])

    if instr.registries:
        lines.append('    registries = []')
        for i, reg in enumerate(instr.registries, start=1):
            obj, extras = _handle_registry(reg)
            if obj:
                lines.append(f'    if (reg := {obj}) is not None:')
                lines.append('        registries.append(reg)')
            if len(extras):
                lines.extend(extras)
        lines.append(f'    a = Assembler({instr.name!r}, registries=registries)')
    else:
        lines.append(f'    a = Assembler({instr.name!r}, flavor=Flavor.{_infer_flavor(instr)})')

    for par in instr.parameters:
        lines.append(f'    a.parameter({str(par)!r})')
    for block in instr.declare:
        lines.append(f'    a.declare({block.source!r}, source={block.filename!r}, line={block.line!r})')
    for block in instr.user:
        lines.append(f'    a.user_vars({block.source!r}, source={block.filename!r}, line={block.line!r})')
    for block in instr.initialize:
        lines.append(f'    a.initialize({block.source!r}, source={block.filename!r}, line={block.line!r})')
    for block in instr.save:
        lines.append(f'    a.save({block.source!r}, source={block.filename!r}, line={block.line!r})')
    for block in instr.final:
        lines.append(f'    a.final({block.source!r}, source={block.filename!r}, line={block.line!r})')
    for md in instr.metadata:
        lines.append(f'    a.metadata(name={md.name!r}, mimetype={md.mimetype!r}, value={md.value!r}, source={md.source.name!r})')

    instance_names: dict[str, str] = {}
    used_vars: set[str] = set()
    groups_by_start = {g.start: g for g in _find_loop_groups(instr.components)} if optimize else {}
    i = 0
    while i < len(instr.components):
        if i in groups_by_start:
            group = groups_by_start[i]
            lines.extend(_emit_loop_group(group, instr.components[group.start:group.end], instance_names))
            i = group.end
            continue

        inst = instr.components[i]
        var_name = _safe_name(inst.name, used_vars)
        instance_names[inst.name] = var_name
        lines.extend(_emit_component(inst, var_name, instance_names))
        i += 1

    lines.extend([
        '    return a.instrument',
        '',
        '',
        "if __name__ == '__main__':",
        '    instrument = build_instrument()',
        '    print(instrument)',
    ])
    return '\n'.join(lines) + '\n'


def save_instr_as_python(instr: Instr, filename: str | Path, optimize: bool = False) -> None:
    Path(filename).write_text(instr_to_python(instr, optimize=optimize))
