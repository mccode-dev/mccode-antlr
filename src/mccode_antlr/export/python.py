from __future__ import annotations

from pathlib import Path

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


def instr_to_python(instr: Instr) -> str:
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
    for inst in instr.components:
        var_name = _safe_name(inst.name, used_vars)
        instance_names[inst.name] = var_name

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

    lines.extend([
        '    return a.instrument',
        '',
        '',
        "if __name__ == '__main__':",
        '    instrument = build_instrument()',
        '    print(instrument)',
    ])
    return '\n'.join(lines) + '\n'


def save_instr_as_python(instr: Instr, filename: str | Path) -> None:
    Path(filename).write_text(instr_to_python(instr))
