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
    start: int
    end: int
    prefix: str
    start_index: int
    at_axis: int
    at_base: int | float
    at_delta: int | float


def _find_loop_groups(components: tuple) -> list[_LoopGroup]:
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
            signatures = [_instance_signature(inst) for inst in chunk]
            if not all(sig == signatures[0] for sig in signatures):
                continue

            at_ref = _ref_name(chunk[0].at_relative[1])
            if at_ref is not None and at_ref in names:
                continue

            vectors = [inst.at_relative[0] for inst in chunk]
            axis_prog = _vector_axis_progression(vectors)
            if axis_prog is None:
                continue
            axis, base, delta = axis_prog
            best = _LoopGroup(start=i, end=j, prefix=series[0], start_index=series[1],
                              at_axis=axis, at_base=base, at_delta=delta)
        if best is not None:
            groups.append(best)
            i = best.end
        else:
            i += 1
    return groups


def _emit_component(inst, var_name: str, instance_names: dict[str, str]) -> list[str]:
    lines = []
    kwargs = [
        f'name={inst.name!r}',
        f'type_name={inst.type.name!r}',
        f'at={_emit_vector_reference(inst.at_relative, instance_names)}',
        f'rotate={_emit_vector_reference(inst.rotate_relative, instance_names)}',
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

    lines.append(f'    {var_name} = a.component({", ".join(kwargs)})')

    if inst.extend:
        blocks = ', '.join(repr(ext.source) for ext in inst.extend)
        lines.append(f'    {var_name}.EXTEND({blocks})')
    if inst.jump:
        jumps = []
        for jump in inst.jump:
            jumps.append(
                f'Jump(target={jump.target!r}, relative_target={jump.relative_target!r}, '
                f'iterate={jump.iterate!r}, condition=Expr.parse({str(jump.condition)!r}), '
                f'absolute_target={jump.absolute_target!r})'
            )
        lines.append(f'    {var_name}.JUMP({", ".join(jumps)})')
    for md in inst.metadata:
        lines.append(
            f'    {var_name}.add_metadata(MetaData('
            f'DataSource.from_type_name_and_name({md.source.type_name!r}, {md.source.name!r}), '
            f'{md.name!r}, {md.mimetype!r}, {md.value!r}))'
        )
    return lines


def _emit_loop_group(group: _LoopGroup, inst, instance_names: dict[str, str]) -> list[str]:
    lines = []
    n = group.end - group.start
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

    kwargs = [
        f'name=f"{group.prefix}{{i + {group.start_index}}}"',
        f'type_name={inst.type.name!r}',
        f'at={at_repr}',
        f'rotate={rotate_repr}',
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

    lines.append(f'        a.component({", ".join(kwargs)})')
    return lines


def _emit_registry(reg, index: int) -> list[str]:
    name = f'reg_{index}'
    if isinstance(reg, LocalRegistry):
        return [f'    {name} = LocalRegistry({reg.name!r}, {reg.root.as_posix()!r}, priority={reg.priority!r})']
    if isinstance(reg, GitHubRegistry):
        return [f'    {name} = GitHubRegistry({reg.name!r}, {reg.url!r}, {reg.version!r}, '
                f'filename={reg.filename!r}, registry={reg.registry!r}, priority={reg.priority!r})']
    if isinstance(reg, ModuleRemoteRegistry):
        return [f'    {name} = ModuleRemoteRegistry({reg.name!r}, {reg.url!r}, '
                f'filename={reg.filename!r}, version={reg.version!r}, priority={reg.priority!r})']
    if isinstance(reg, RemoteRegistry):
        return [f'    {name} = RemoteRegistry({reg.name!r}, {reg.url!r}, {reg.version!r}, '
                f'{reg.filename!r}, priority={reg.priority!r})']
    if isinstance(reg, InMemoryRegistry):
        lines = [f'    {name} = InMemoryRegistry({reg.name!r}, priority={reg.priority!r})']
        for comp_name, source in reg.components.items():
            lines.append(f'    {name}.add({comp_name!r}, {source!r})')
        return lines
    return [f'    # Unsupported registry type preserved as comment: {type(reg).__name__}({reg!r})',
            f'    {name} = None']


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
    lines.extend(['', '', 'def build_instrument():'])

    if instr.registries:
        lines.append('    registries = []')
        for i, reg in enumerate(instr.registries, start=1):
            lines.extend(_emit_registry(reg, i))
            lines.append(f'    if reg_{i} is not None:')
            lines.append(f'        registries.append(reg_{i})')
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
            lines.extend(_emit_loop_group(group, instr.components[group.start], instance_names))
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
