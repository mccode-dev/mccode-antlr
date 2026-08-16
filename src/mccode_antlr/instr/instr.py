"""Data structures required for representing the contents of a McCode instr file"""
from __future__ import annotations

from functools import lru_cache
from io import StringIO
from pathlib import Path
from msgspec import Struct, field
from typing import Optional
from ..common import InstrumentParameter, MetaData, parameter_name_present, RawC, blocks_to_raw_c, Expr
from ..reader import Registry
from .instance import Instance, DepInstance, Comp
from .group import Group, DependentGroup
from loguru import logger


class Instr(Struct):
    """Intermediate representation of a McCode instrument

    Read from a .instr file -- possibly including more .comp and .instr file sources
    For output to a runtime source file
    """
    name: Optional[str] = None  # Instrument name, e.g. {name}.instr (typically)
    source: Optional[str] = None  # Instrument *file* name
    parameters: tuple[InstrumentParameter, ...] = field(default_factory=tuple)  # runtime-set instrument parameters
    metadata: tuple[MetaData, ...] = field(default_factory=tuple)  # metadata for use by simulation consumers
    components: tuple[Instance, ...] = field(default_factory=tuple)  #
    included: tuple[Instr, ...] = field(default_factory=tuple)  # Instr(s) %include-d into this one's TRACE
    user: tuple[RawC, ...] = field(default_factory=tuple)  # struct members for _particle
    declare: tuple[RawC, ...] = field(default_factory=tuple)  # global parameters used in component trace
    initialize: tuple[RawC, ...] = field(default_factory=tuple)  # initialization of global declare parameters
    save: tuple[RawC, ...] = field(default_factory=tuple)  # statements executed after TRACE to save results
    final: tuple[RawC, ...] = field(default_factory=tuple)  # clean-up memory for global declare parameters
    registries: tuple[Registry, ...] = field(default_factory=tuple)  # the registries used by the reader to populate this
    dependency: tuple[str, ...] = field(default_factory=tuple)  # some (C) flags needed for compilation of the (translated) instrument
    flow_edges: tuple = field(default_factory=tuple)  # serialisable particle-flow edge records (FlowEdgeRecord)

    @classmethod
    def from_dict(cls, args: dict):
        from mccode_antlr.reader.registry import SerializableRegistry as SR
        from mccode_antlr.reader.registry import screen_deserialized_registries
        from mccode_antlr.instr.instance import make_independent
        from mccode_antlr.instr.flow import FlowEdgeRecord
        popt = 'name', 'source'
        tpreq = 'dependency',
        tmtype = {'parameters': InstrumentParameter, 'metadata': MetaData,
                 'instances': DepInstance, 'user': RawC, 'declare': RawC,
                  'initialize': RawC, 'save': RawC, 'final': RawC, 'registries': SR
                 }
        dtype = {'components': Comp}

        data = {}
        data.update({k: args[k] for k in popt if k in args})
        data.update({k: tuple(a for a in args[k]) for k in tpreq})
        data.update({k: tuple(t.from_dict(a) for a in args[k]) for k, t in tmtype.items()})
        data.update({k: {n: t.from_dict(v) for n, v in args[k].items()} for k, t in dtype.items()})

        name = data.get('name', '<unnamed>')
        data['registries'] = tuple(
            screen_deserialized_registries(
                data['registries'], f'serialized instrument {name!r}'
            )
        )

        instances = data.pop('instances')
        components = data.pop('components')
        data['components'] = make_independent(instances, components)
        data['flow_edges'] = tuple(FlowEdgeRecord.from_dict(a) for a in args.get('flow_edges', []))
        data['included'] = tuple(cls.from_dict(a) for a in args.get('included', ()))
        instr = cls(**data)
        _restore_included_components(instr)
        return instr

    def to_dict(self):
        from msgspec.structs import fields
        from mccode_antlr.reader.registry import SerializableRegistry as SR
        from mccode_antlr.io.portable import with_embedded_files
        data = {k.name: getattr(self, k.name) for k in fields(self)}
        instances = tuple(DepInstance.from_independent(inst) for inst in self.components)
        components = {inst.type.name: inst.type for inst in self.components}

        data['registries'] = [SR.from_registry(r)
                              for r in with_embedded_files(self.registries, self)]
        data['instances'] = instances
        data['components'] = components
        data['included'] = tuple(child._to_included_dict() for child in self.included)
        return data

    def _to_included_dict(self) -> dict:
        """Serialized form of an included child: instances live only in the top-level dict."""
        d = self.to_dict()  # recursion covers grandchildren
        d['instances'] = ()
        d['components'] = {}
        return d

    def __eq__(self, other):
        if not isinstance(other, Instr):
            return NotImplemented
        from msgspec.structs import fields
        for name in [f.name for f in fields(self)]:
            if getattr(self, name) != getattr(other, name):
                return False
        return True

    def __hash__(self):
        return hash((
            self.name, self.source, self.parameters, self.metadata, self.components,
            self.included, self.user, self.declare, self.initialize, self.save,
            self.final, self.registries, self.dependency
        ))

    def to_file(self, output=None, wrapper=None, flat: bool = True):
        if output is None:
            output = StringIO()
        if wrapper is None:
            from mccode_antlr.common import TextWrapper
            wrapper = TextWrapper(width=120)
        if flat or not self.included:
            sections = {key: getattr(self, key)
                        for key in ('parameters', 'metadata', 'declare', 'user',
                                    'initialize', 'save', 'final', 'dependency')}
            owners = {}
        else:
            sections, owners = self._hierarchical_view()
        print(wrapper.start_block_comment(f"Instrument {self.name or 'None'}"), file=output)
        print(wrapper.line('Instrument:', [self.name or 'None']), file=output)
        print(wrapper.line('Source:', [self.source or 'None']), file=output)
        print(wrapper.line('Contains:', [f'"%include {include.name}"' for include in self.included]), file=output)
        print(wrapper.line('Registries:', [registry.name for registry in self.registries]), file=output)
        for registry in self.registries:
            registry.to_file(output=output, wrapper=wrapper)
        print(wrapper.end_block_comment(), file=output)

        instr_parameters = wrapper.hide(', '.join(p.to_string(wrapper=wrapper) for p in sections['parameters']))
        first_line = wrapper.line('DEFINE INSTRUMENT', [f"{self.name or 'None'}({instr_parameters})"])
        print(first_line, file=output)

        for metadata in sections['metadata']:
            metadata.to_file(output=output, wrapper=wrapper)
        # Print only the .instr-added DEPENDENCY line(s) here -- .comp DEPENDENCY excluded
        if sections['dependency']:
            print(wrapper.quoted_line('DEPENDENCY ', list(sections['dependency'])), file=output)

        if sections['declare']:
            print(wrapper.block('DECLARE', _join_raw_tuple(sections['declare'])), file=output)
        if sections['user']:
            print(wrapper.block('USERVARS', _join_raw_tuple(sections['user'])), file=output)
        if sections['initialize']:
            print(wrapper.block('INITIALIZE', _join_raw_tuple(sections['initialize'])), file=output)

        print(wrapper.start_list('TRACE'), file=output)
        emitted = set()
        previous_owner = None
        for instance in self.components:
            owner = owners.get(instance.source)
            if owner is not None:
                if owner.name not in emitted:
                    emitted.add(owner.name)
                    print(wrapper.start_list_item(), file=output)
                    print(wrapper.line('%include', [f'"{owner.name}.instr"']), file=output)
                    print(wrapper.end_list_item(), file=output)
                elif previous_owner is not owner:
                    logger.warning(
                        f'Instance {instance.name} from {owner.name} is not contiguous with its'
                        f' %include group; it will appear at a shifted position when reparsed')
                previous_owner = owner
                continue
            previous_owner = None
            print(wrapper.start_list_item(), file=output)
            instance.to_file(output, wrapper)
            print(wrapper.end_list_item(), file=output)
        if sections['save']:
            print(wrapper.block('SAVE', _join_raw_tuple(sections['save'])), file=output)
        if sections['final']:
            print(wrapper.block('FINALLY', _join_raw_tuple(sections['final'])), file=output)
        print(wrapper.end_list('END'), file=output)

    def _included_tree_names(self) -> list:
        """This instrument's name plus every name in its included tree (with duplicates, for checking)."""
        names = [self.name]
        for child in self.included:
            names += child._included_tree_names()
        return names

    def _hierarchical_view(self) -> tuple[dict, dict]:
        """(sections, owners) for non-flat writing.

        `sections` maps each merged-content field name to a tuple with all
        included-child content subtracted by equality; `owners` maps every
        source-tag name in the included tree to its TOP-LEVEL child Instr.
        """
        sections = {key: getattr(self, key)
                    for key in ('parameters', 'metadata', 'declare', 'user',
                                'initialize', 'save', 'final', 'dependency')}
        warn = {'declare', 'user', 'initialize', 'save', 'final'}
        for child in self.included:
            for key in sections:
                sections[key] = _subtract_tuple(sections[key], getattr(child, key), key in warn)
        owners = {}
        for child in self.included:
            for name in child._included_tree_names():
                owners[name] = child
        return sections, owners

    def to_strings(self, wrapper=None) -> dict[str, str]:
        """{'{name}.instr': content} for this instrument and its included tree.

        Same content `to_files` writes to disk, but held in memory -- lets a
        caller (e.g. `io/extract.py`'s manifest builder) inspect the
        instrument hierarchy without touching the filesystem.
        """
        names = self._included_tree_names()
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise RuntimeError(f'Cannot write instrument hierarchy with duplicated names {duplicates}')
        result = {}
        for child in self.included:
            result.update(child.to_strings(wrapper=wrapper))
        output = StringIO()
        self.to_file(output, wrapper, flat=False)
        result[f'{self.name}.instr'] = output.getvalue()
        return result

    def to_files(self, directory, wrapper=None) -> Path:
        """Write this instrument and its included tree as one .instr file each.

        The parent file contains `%include "{child}.instr"` directives in place
        of the merged content; each included Instr is written (recursively) to
        `{child.name}.instr` in the same directory. Returns the parent's path.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in self.to_strings(wrapper).items():
            (directory / name).write_text(content)
        return directory / f'{self.name}.instr'

    def to_string(self, wrapper):
        from io import StringIO
        output = StringIO()
        self.to_file(output, wrapper)
        return output.getvalue()

    def __str__(self):
        from mccode_antlr.common import TextWrapper
        return self.to_string(TextWrapper())

    def _repr_html_(self):
        from mccode_antlr.common import HTMLWrapper
        wrapper = HTMLWrapper()
        output = StringIO()
        self.to_file(output=output, wrapper=wrapper)
        body = output.getvalue()
        return f'<div class="mccode-instr">{body}</div>'

    def add_component(self, a: Instance):
        if any(x.name == a.name for x in self.components):
            raise RuntimeError(f"A component instance named {a.name} is already present in the instrument")
        prev = self.components[-1] if self.components else None
        self.components += (a,)
        if prev is not None:
            self._add_sequential_or_group_edge(prev, a)

    def add_flow_edge(self, src: str, dst: str, edge) -> None:
        """Append a single :class:`~mccode_antlr.instr.FlowEdgeRecord` to ``flow_edges``.

        Args:
            src: Source component instance name.
            dst: Destination component instance name.
            edge: Any :class:`~mccode_antlr.instr.flow.FlowEdge` subclass instance.
        """
        from .flow import FlowEdgeRecord
        self.flow_edges += (FlowEdgeRecord(src=src, dst=dst, edge=edge),)

    def _add_sequential_or_group_edge(self, prev: Instance, curr: Instance) -> None:
        """Add the correct sequential or group flow edge when *curr* is appended after *prev*."""
        from .flow import FlowEdgeRecord, SequentialEdge, GroupEdge, GroupEdgeKind
        same_group = prev.group is not None and prev.group == curr.group
        prev_exits_group = prev.group is not None and prev.group != (curr.group or '')

        if same_group:
            self.flow_edges += (FlowEdgeRecord(
                src=prev.name, dst=curr.name,
                edge=GroupEdge(group_name=prev.group, kind=GroupEdgeKind.TRY_NEXT),
            ),)
        elif prev_exits_group:
            # prev is the last member of its group; add group-exit edges from all group members to curr
            group_name = prev.group
            members = [inst for inst in self.components if inst.group == group_name]
            for member in members:
                self.flow_edges += (FlowEdgeRecord(
                    src=member.name, dst=curr.name,
                    edge=GroupEdge(group_name=group_name, kind=GroupEdgeKind.SCATTER_EXIT),
                ),)
            self.flow_edges += (FlowEdgeRecord(
                src=prev.name, dst=curr.name,
                edge=GroupEdge(group_name=group_name, kind=GroupEdgeKind.PASS_THROUGH),
            ),)
        else:
            self.flow_edges += (FlowEdgeRecord(
                src=prev.name, dst=curr.name,
                edge=SequentialEdge(when=curr.when),
            ),)

    def finalize_flow_edges(self) -> None:
        """Add JUMP edges to ``flow_edges`` (deferred because forward targets are unknown during parsing)."""
        from .flow import FlowEdgeRecord, JumpEdge
        components = self.components
        n = len(components)
        name_to_idx = {inst.name: idx for idx, inst in enumerate(components)}
        for inst in components:
            for jmp in inst.jump:
                target_idx = jmp.absolute_target
                if target_idx < 0:
                    target_idx = name_to_idx.get(jmp.target, -1)
                if 0 <= target_idx < n:
                    self.flow_edges += (FlowEdgeRecord(
                        src=inst.name, dst=components[target_idx].name,
                        edge=JumpEdge(
                            condition=jmp.condition,
                            iterate=jmp.iterate,
                            absolute_target=target_idx,
                        ),
                    ),)

    def build_flow_graph(self):
        """Rebuild ``flow_edges`` from scratch and return the derived :class:`networkx.MultiDiGraph`.

        This is idempotent; it replaces any existing ``flow_edges`` content.
        """
        from .flow import _build_flow_edge_records, flow_graph_from_records
        self.flow_edges = _build_flow_edge_records(self.components)
        return flow_graph_from_records(self.components, self.flow_edges)

    @property
    def flow_graph(self):
        """Derive a :class:`networkx.MultiDiGraph` from the current ``flow_edges`` (read-only view).

        Call :meth:`build_flow_graph` to (re)build ``flow_edges`` from the component list,
        or use :meth:`finalize_flow_edges` to add JUMP edges after incremental construction.
        """
        from .flow import flow_graph_from_records
        return flow_graph_from_records(self.components, self.flow_edges)

    def insert_component(
        self,
        name: str,
        component,
        *,
        before: Optional[str] = None,
        after: Optional[str] = None,
        at_relative: Optional[tuple] = None,
        rotate_relative: Optional[tuple] = None,
        parameters: tuple = (),
        group: Optional[str] = None,
        removable: bool = False,
    ) -> Instance:
        """Insert a new component instance before or after an existing one.

        Exactly one of *before* or *after* must be specified.

        The ``components`` tuple is updated in-place and ``flow_edges`` is
        updated consistently: the connecting sequential or TRY_NEXT edge
        between the two surrounding components is split into two edges.  All
        ``Jump.absolute_target`` fields in all existing instances are reset to
        ``-1``; the translator's ``set_jump_absolute_targets()`` (called during
        C generation) will re-resolve them by name.

        Parameters
        ----------
        name:
            Instance name for the new component (must be unique).
        component:
            Component type: a :class:`~mccode_antlr.instr.Comp` object or a
            string that will be looked up from the instrument's registries.
        before:
            Name of the existing component to insert *before*.
        after:
            Name of the existing component to insert *after*.
        at_relative:
            ``(Vector | tuple[float,float,float], Instance | str | None)``
            position and reference.  The reference may name a component that
            comes *after* the new instance in the final order; it will be
            re-expressed relative to the predecessor component.  If ``None``,
            the position is computed as the midpoint between the surrounding
            components (falls back to the origin of the predecessor when
            orientations are unavailable or non-constant).
        rotate_relative:
            ``(Angles | tuple[float,float,float], Instance | str | None)``
            rotation and reference.  Same forward-reference fixing applies.
            If ``None``, the absolute orientation of the downstream component
            is used (falls back to zero-rotation RELATIVE predecessor).
        parameters:
            Component instance parameters.
        group:
            GROUP name for the new instance, if any.
        removable:
            Whether the instance is marked removable.

        Returns
        -------
        Instance
            The newly created instance (already inserted into
            ``self.components``).

        Raises
        ------
        ValueError
            If neither or both of *before*/*after* are given, or if *name*
            is already present, or if the reference component is not found.
        """
        from .flow import FlowEdgeRecord, SequentialEdge, GroupEdge, GroupEdgeKind

        # ── 0. Validate ────────────────────────────────────────────────────────
        if (before is None) == (after is None):
            raise ValueError("Exactly one of 'before' or 'after' must be specified.")
        if any(x.name == name for x in self.components):
            raise ValueError(f"A component instance named {name!r} is already present.")

        # ── 1. Resolve reference component and insertion index ─────────────────
        comp_names = [c.name for c in self.components]
        if before is not None:
            ref_name = before if isinstance(before, str) else before.name
            if ref_name not in comp_names:
                raise ValueError(f"Component {ref_name!r} not found.")
            insert_idx = comp_names.index(ref_name)
            pred_inst = self.components[insert_idx - 1] if insert_idx > 0 else None
            succ_inst = self.components[insert_idx]
        else:
            ref_name = after if isinstance(after, str) else after.name
            if ref_name not in comp_names:
                raise ValueError(f"Component {ref_name!r} not found.")
            target_idx = comp_names.index(ref_name)
            insert_idx = target_idx + 1
            pred_inst = self.components[target_idx]
            succ_inst = self.components[insert_idx] if insert_idx < len(self.components) else None

        # ── 2. Resolve component type ──────────────────────────────────────────
        if isinstance(component, str):
            from ..reader import Reader
            reader = Reader(registries=list(self.registries))
            component = reader.get_component(component)

        # ── 3. Auto-compute position / rotation if not provided ────────────────
        orientations = self.resolve_orientations()
        if at_relative is None:
            at_relative = _midpoint_at_relative(pred_inst, succ_inst, orientations)
        if rotate_relative is None:
            rotate_relative = _downstream_rotate_relative(pred_inst, succ_inst, orientations)

        # ── 4. Normalise vector/angles in at_relative / rotate_relative ────────
        from .orientation import Vector, Angles
        at_relative = _normalise_vr(at_relative, self.components, Vector)
        rotate_relative = _normalise_vr(rotate_relative, self.components, Angles)

        # ── 5. Fix forward references (ref must come before the new instance) ──
        at_relative = _fix_forward_ref(at_relative, insert_idx, pred_inst, orientations)
        rotate_relative = _fix_forward_ref_rotation(rotate_relative, insert_idx, pred_inst, orientations)

        # ── 6. Reject insertion that would break a contiguous group ───────────
        if (pred_inst is not None and succ_inst is not None
                and pred_inst.group is not None
                and pred_inst.group == succ_inst.group
                and group != pred_inst.group):
            raise ValueError(
                f"Cannot insert component {name!r} (group={group!r}) between group members "
                f"{pred_inst.name!r} and {succ_inst.name!r} "
                f"(group {pred_inst.group!r}): McCode requires groups to be contiguous. "
                f"Insert before {pred_inst.name!r}, after the last member of the group, "
                f"or pass group={pred_inst.group!r} to join the group."
            )

        # ── 7. Create the instance ────────────────────────────────────────────────
        new_inst = Instance(name, component, at_relative, rotate_relative,
                            parameters=parameters, group=group, removable=removable)

        # ── 8. Insert into components tuple ────────────────────────────────────
        comps = list(self.components)
        comps.insert(insert_idx, new_inst)
        self.components = tuple(comps)

        # ── 9. Update flow_edges: split the connecting positional edge ─────────
        updated_edges = list(self.flow_edges)
        if pred_inst is not None and succ_inst is not None:
            pred_name, succ_name = pred_inst.name, succ_inst.name
            # Find the single "positional" edge: SequentialEdge or TRY_NEXT between pred and succ
            connecting_idx = next(
                (i for i, r in enumerate(updated_edges)
                 if r.src == pred_name and r.dst == succ_name
                 and isinstance(r.edge, (SequentialEdge, GroupEdge))
                 and not (isinstance(r.edge, GroupEdge)
                          and r.edge.kind in (GroupEdgeKind.SCATTER_EXIT,
                                              GroupEdgeKind.PASS_THROUGH))),
                None,
            )
            if connecting_idx is not None:
                old_edge = updated_edges.pop(connecting_idx).edge
                if isinstance(old_edge, GroupEdge) and old_edge.kind == GroupEdgeKind.TRY_NEXT:
                    if group == pred_inst.group:
                        e1 = GroupEdge(group_name=pred_inst.group, kind=GroupEdgeKind.TRY_NEXT)
                        e2 = GroupEdge(group_name=pred_inst.group, kind=GroupEdgeKind.TRY_NEXT)
                    else:
                        e1 = SequentialEdge(when=new_inst.when)
                        e2 = SequentialEdge(when=succ_inst.when)
                else:
                    e1 = SequentialEdge(when=new_inst.when)
                    e2 = SequentialEdge(when=succ_inst.when)
                updated_edges.append(FlowEdgeRecord(src=pred_name, dst=name, edge=e1))
                updated_edges.append(FlowEdgeRecord(src=name, dst=succ_name, edge=e2))
        elif pred_inst is None and succ_inst is not None:
            updated_edges.append(FlowEdgeRecord(
                src=name, dst=succ_inst.name, edge=SequentialEdge(when=succ_inst.when),
            ))
        elif pred_inst is not None and succ_inst is None:
            updated_edges.append(FlowEdgeRecord(
                src=pred_inst.name, dst=name, edge=SequentialEdge(when=new_inst.when),
            ))
        self.flow_edges = tuple(updated_edges)

        # ── 10. Invalidate all Jump.absolute_target fields ─────────────────────
        # The translator's set_jump_absolute_targets() re-resolves these by name.
        for inst in self.components:
            for jmp in inst.jump:
                jmp.absolute_target = -1

        return new_inst

    def add_parameter(self, a: InstrumentParameter, ignore_repeated=False):
        if not parameter_name_present(self.parameters, a.name):
            self.parameters += (a,)
        elif not ignore_repeated:
            raise RuntimeError(f"An instrument parameter named {a.name} is already present in the instrument")

    def get_parameter(self, name, default=None):
        if parameter_name_present(self.parameters, name):
            for parameter in self.parameters:
                if name == parameter.name:
                    return parameter
        return default

    def has_parameter(self, name):
        return parameter_name_present(self.parameters, name)

    def last_component(self, count: int = 1, removable_ok: bool = True):
        if len(self.components) < count:
            raise RuntimeError(f"Only {len(self.components)} components defined -- can not go back {count}.")
        if removable_ok:
            return self.components[-count]
        fixed = [comp for comp in self.components if not comp.removable]
        if len(fixed) < count:
            for comp in self.components:
                logger.info(f'{comp.name}')
            raise RuntimeError(f"Only {len(fixed)} fixed components defined -- can not go back {count}.")
        return fixed[-count]

    def get_component(self, name: str):
        if name == 'PREVIOUS':
            return self.components[-1]
        for comp in self.components:
            if comp.name == name:
                return comp
        raise RuntimeError(f"No component instance named {name} defined.")

    def has_component_named(self, name: str):
        return any(comp.name == name for comp in self.components)

    def get_component_names_by_category(self, category: str):
        """Find all component instance names for a given category.

        Note:
            The category of an instance is determined by its type, and is either
            - set inside the .comp file by a 'CATEGORY <category>' directive, or
            - *guessed* by the reader based on the path to the .comp file.
            The second behaviour is to match McStasScript/McCode-3, which does not work for user-defined components.
        """
        return [inst.name for inst in self.components if category in inst.type.category]

    def include(self, child: Instr) -> Instr:
        """Merge an already-parsed Instr into this one, keeping provenance.

        Implements TRACE `%include` semantics: parameters merge first-wins,
        metadata merges by name (child replaces), C blocks concatenate,
        DEPENDENCY flags merge de-duplicated, and non-removable child
        component instances are appended, tagged with `source=child.name`
        unless already tagged by a deeper include. The child is absorbed:
        its `components` tuple is trimmed to the merged instances (sharing
        the same Instance objects with this instrument) and the child is
        stored in `self.included`. Registries are NOT merged here (see
        `Assembler.include`).

        A child that was already absorbed elsewhere is refused (its instances
        would be shared between two instruments); pass `child.detached()`
        instead. Detection relies on instance tags, so an absorbed child with
        no component instances is not caught -- sharing of bare code blocks is
        accepted as low-risk.
        """
        if any(x.source == child.name for x in child.components):
            raise RuntimeError(
                f"{child.name!r} appears to have already been included into an instrument: its component "
                f"instances carry its own name as their source tag, and including it again would share the "
                f"same Instance objects between two instruments (mutations through one would silently affect "
                f"the other, while serialization would still split them). Include a detached copy instead: "
                f"parent.include(child.detached())"
            )
        overlap = set(self._included_tree_names()) & set(child._included_tree_names())
        if overlap:
            raise RuntimeError(
                f"Cannot include {child.name!r} into {self.name!r}: instrument name(s) {sorted(overlap)} would "
                f"appear more than once in the include tree. Including the same instrument multiple times is "
                f"not representable, even in the McCode-legal case where all non-removable instances are COPY "
                f"auto-named, because auto-generated instance names depend on their position."
            )
        for instance in child.components:
            if not instance.removable and any(x.name == instance.name for x in self.components):
                raise RuntimeError(f"Cannot include {child.name!r}: component instance {instance.name!r} already present")
        removable = sum(1 for x in child.components if x.removable)
        if removable:
            logger.info(f'Dropping {removable} REMOVABLE component instance(s) of included instrument {child.name}')
            child.components = tuple(x for x in child.components if not x.removable)
        # Tag BEFORE add_component so instance hashes are stable before anything caches them
        for instance in child.components:
            if instance.source is None:
                instance.source = child.name
        for par in child.parameters:
            self.add_parameter(par, ignore_repeated=True)
        for meta in child.metadata:
            self.add_metadata(meta)
        if len(child.declare):
            self.declare += child.declare
        if len(child.user):
            self.user += child.user
        if len(child.initialize):
            self.initialize += child.initialize
        if len(child.save):
            self.save += child.save
        if len(child.final):
            self.final += child.final
        # NOTE behavior change: the old visitor merge silently dropped the child's DEPENDENCY
        self.dependency += tuple(d for d in child.dependency if d not in self.dependency)
        for instance in child.components:
            self.add_component(instance)
        self.included += (child,)
        return child

    def DEPENDENCY(self, *strings):
        self.dependency += strings

    def USERVARS(self, *blocks):
        self.user += blocks_to_raw_c(*blocks)

    def DECLARE(self, *blocks):
        self.declare += blocks_to_raw_c(*blocks)

    def INITIALIZE(self, *blocks):
        self.initialize += blocks_to_raw_c(*blocks)

    def SAVE(self, *blocks):
        self.save += blocks_to_raw_c(*blocks)

    def FINALLY(self, *blocks):
        self.final += blocks_to_raw_c(*blocks)

    def add_metadata(self, m: MetaData):
        if any([x.name == m.name for x in self.metadata]):
            self.metadata = tuple([x for x in self.metadata if x.name != m.name])
        self.metadata += (m,)

    @property
    def groups(self):
        return determine_groups(self.components)

    def component_types(self):
        # # If component order is unimportant, we can use a set:
        # return set(inst.type for inst in self.components)
        # For comparison with the C code generator, we must keep the order of component definitions
        return list(dict.fromkeys([inst.type for inst in self.components]))

    def collect_metadata(self):
        """Component definitions and instances can define metadata too, collect it all together here"""
        # Metadata defined in an instance overrides that defined in a component.
        # Metadata defined for an instrument is added to the collected list
        return tuple(m for inst in self.components for m in inst.collect_metadata()) + self.metadata

    def _getpath(self, filename: str):
        from pathlib import Path
        for registry in self.registries:
            if registry.known(filename):
                return registry.path(filename).absolute().resolve()
        return Path()

    def _replace_env_getpath_cmd(self, flags: str):
        """Replace CMD, ENV, and GETPATH directives from a flag string"""

        # Mimics McCode-3/tools/Python/mccodelib/cflags.py:evaluate_dependency_str
        #
        def getpath(chars):
            return self._getpath(chars).as_posix()

        def eval_cmd(chars):
            from mccode_antlr.utils import run_prog_message_output
            from shlex import split
            message, output = run_prog_message_output(split(chars))
            if message:
                raise RuntimeError(f"Calling {chars} resulted in error {message}")
            output = [line.strip() for line in output.splitlines() if line.strip()]
            if len(output) > 1:
                raise RuntimeError(f"Calling {chars} produced more than one line of output")
            return output[0] if output else ''

        def eval_env(chars):
            from os import environ
            return environ.get(chars, '')

        def replace(chars, start, replacer):
            if start not in chars:
                return chars
            before, after = chars.split(start, 1)
            if '(' != after[0]:
                raise ValueError(f'Missing opening parenthesis in dependency string after {start}')
            if ')' not in after:
                raise ValueError(f'Missing closing parenthesis in dependency string after {start}')
            dep, after = after[1:].split(')', 1)
            if start in dep:
                raise ValueError(f'Nested {start} in dependency string')
            return before + replacer(dep) + replace(after, start, replacer)

        for key, worker in zip(['ENV', 'GETPATH', 'CMD'], [eval_env, getpath, eval_cmd]):
            flags = replace(flags, key, worker)

        return flags

    def _replace_keywords(self, flag):
        from mccode_antlr.config import config
        from mccode_antlr.config.fallback import regex_sanitized_config_fallback
        from re import sub, findall
        if '@NEXUSFLAGS@' in flag:
            flag = sub(r'@NEXUSFLAGS@', config['flags']['nexus'].as_str_expanded(), flag)
        if '@MCCODE_LIB@' in flag:
            print(f'The instrument {self.name} uses @MCCODE_LIB@ dependencies which no longer work.')
            print('Expect problems at compilation.')
            flag = sub('@MCCODE_LIB@', '.', flag)
        general_re = r'@(\w+)@'
        for replace in findall(general_re, flag):
            # Is this replacement something like XXXFLAGS?
            if replace.lower().endswith('flags'):
                replacement = regex_sanitized_config_fallback(config['flags'], replace.lower()[:-5])
                flag = sub(f'@{replace}@', replacement, flag)
            else:
                logger.warning(f'Unknown keyword @{replace}@ in dependency string')
        return flag

    @property
    def dependencies(self) -> set[str]:
        # Each 'flag' in self.flags is from a single instrument component DEPENDENCY,
        # and might contain duplicates: If we accept that white space differences
        # matter, we can deduplicate the strings 'easily'
        uf = set(self.dependency)
        uf.update(inst.dependency for inst in self.components if inst.dependency is not None)
        if any(inst.cpu for inst in self.components):
            uf.add('-DFUNNEL')
        return uf

    def decoded_flags(self) -> list[str]:
        # The dependency strings are allowed to contain any of
        #       '@NEXUSFLAGS@', @MCCODE_LIB@, CMD(...), ENV(...), GETPATH(...)
        # each of which should be replaced by ... something. Start by replacing the 'static' (old-style) keywords
        replaced_flags = [self._replace_keywords(flag) for flag in self.dependencies]
        # Then use the above decoder method to replace any instances of CMD, ENV, or GETPATH
        return [self._replace_env_getpath_cmd(flag) for flag in replaced_flags]

    def copy(self, first=0, last=-1):
        """Return a copy of this instrument, optionally with only a subset of components"""
        from copy import deepcopy
        copy = Instr(self.name, self.source)
        copy.parameters = tuple(x for x in self.parameters)
        copy.metadata = tuple(x.copy() for x in self.metadata)
        if last < 0:
            last += 1 + len(self.components)
        copy.components = tuple(x.copy() for x in self.components[first:last])
        copy.included = tuple(x.copy() for x in self.included)
        copy.user = tuple(x.copy() for x in self.user)
        copy.declare = tuple(x.copy() for x in self.declare)
        copy.initialize = tuple(x.copy() for x in self.initialize)
        copy.save = tuple(x.copy() for x in self.save)
        copy.final = tuple(x.copy() for x in self.final)
        # copy.groups = {k: v.copy() for k, v in self.groups.items()}
        copy.dependency = tuple(x for x in self.dependency)
        copy.registries = tuple(x for x in self.registries)
        _restore_included_components(copy)
        return copy

    def detached(self) -> Instr:
        """A copy safe to `include` into another instrument.

        Instances are fresh objects (via `copy`) and this instrument's own
        provenance tags are cleared so `include` will re-tag them; tags from
        deeper nested includes are preserved.
        """
        dup = self.copy()
        for instance in dup.components:
            if instance.source == dup.name:
                instance.source = None
        return dup

    def split(self, at, remove_unused_parameters=False):
        """Produces two instruments, both containing the indicated component

        Parameters:
        -----------
        after: Union[Instance, str]
            A component instance or the _name_ of a component instance at which to split the instrument.
            The instance or one with a matching name _must_ be in the instrument, and should probably be an Arm.
        remove_unused_parameters: bool
            If True, any Instrument parameters which do not appear in instance definitions or code blocks is not
            included in the output instruments

        Return:
        -------
        tuple[Instr, Instr]
            The first Instr has components up to and including the split-point.
            The second Instr has components starting from the split-point.
        """
        if isinstance(at, Instance):
            index = self.components.index(at)
        elif isinstance(at, str):
            index = [i for i, x in enumerate(self.components) if x.name == at]
            if len(index) != 1:
                raise RuntimeError(f'Can only split an instrument after a single component, "{at}" matches {index}')
            index = index[0]
        else:
            raise RuntimeError('Can only split an instrument after a component or component name')
        first = self.copy(last=index + 1)
        first.name = self.name + '_first'
        if first.check_instrument_parameters(remove=remove_unused_parameters) and not remove_unused_parameters:
            logger.warning(f'Instrument {first.name} has unused instrument parameters')

        orig_orientations = self.resolve_orientations()
        second = self.copy(first=index)
        second.name = self.name + '_second'
        # remove any dangling component references and re-reference into the new instrument's components:
        for instance in second.components:
            at_rel = instance.at_relative[1]
            rot_rel = instance.rotate_relative[1]
            if isinstance(at_rel, Instance):
                if second.has_component_named(at_rel.name):
                    instance.at_relative = instance.at_relative[0], second.get_component(at_rel.name)
                else:
                    instance.at_relative = orig_orientations[instance.name].position(), None
            if isinstance(rot_rel, Instance):
                if second.has_component_named(rot_rel.name):
                    instance.rotate_relative = instance.rotate_relative[0], second.get_component(rot_rel.name)
                else:
                    instance.rotate_relative = orig_orientations[instance.name].angles(), None
        if second.check_instrument_parameters(remove=remove_unused_parameters) and not remove_unused_parameters:
            logger.info(f'Instrument {second.name} has unused instrument parameters')

        # A split instrument no longer corresponds to any file hierarchy
        for part in (first, second):
            part.included = ()
            for instance in part.components:
                instance.source = None

        return first, second

    def make_instance(self, name, component, at_relative=None, rotate_relative=None,
                      parameters=None, group=None, removable=False):
        if parameters is None:
            parameters = tuple()
        if any(x.name == name for x in self.components):
            raise RuntimeError(f"An instance named {name} is already present in the instrument")
        if isinstance(component, str):
            from ..reader import Reader
            reader = Reader(registries=list(self.registries))
            component = reader.get_component(component)
        self.components += (Instance(name, component, at_relative, rotate_relative,
                                     parameters=parameters, group=group, removable=removable),)

    def resolve_orientations(self) -> dict:
        """Resolve absolute orientations for every component in declaration order.

        Returns a ``dict[str, Orient]`` mapping each component name to its
        fully-resolved absolute :class:`~mccode_antlr.instr.orientation.Orient`.
        Components must reference only earlier-defined components, which is
        enforced by the McCode language, so the list is already topologically
        sorted.
        """
        from .orientation import Orient
        resolved: dict = {}
        for inst in self.components:
            at, at_ref = inst.at_relative
            rt, rt_ref = inst.rotate_relative
            ar = resolved.get(at_ref.name) if at_ref is not None else None
            rr = resolved.get(rt_ref.name) if rt_ref is not None else None
            if at_ref is rt_ref:
                resolved[inst.name] = Orient.from_dependent_orientation(ar, at, rt)
            else:
                resolved[inst.name] = Orient.from_dependent_orientations(ar, at, rr, rt)
        return resolved

    def mcpl_split(self,
                   after,
                   filename=None,
                   output_component=None,
                   output_parameters=None,
                   input_component=None,
                   input_parameters=None,
                   remove_unused_parameters=False
                   ):
        from ..common import ComponentParameter
        from ..common import Expr
        from .orientation import Vector, Angles
        if filename is None:
            filename = self.name + '.mcpl'
        if filename[0] != '"' or filename[-1] != '"':
            filename = '"' + filename + '"'

        filename_parameter = ComponentParameter('filename', Expr.parameter('mcpl_filename'))
        first, second = self.split(after, remove_unused_parameters=remove_unused_parameters)
        mcpl_filename = InstrumentParameter.parse(f'string mcpl_filename = {filename}')
        first.add_parameter(mcpl_filename)
        second.add_parameter(mcpl_filename)

        fc = first.components[-1]
        if fc.type.name != 'Arm':
            logger.info(f'Component {after} is a {fc.type.name} instead of an Arm -- using MCPL file may cause problems')

        if output_component is None:
            output_component = 'MCPL_output'
        if output_parameters is None:
            output_parameters = (filename_parameter,)
        elif not any(p.name == 'filename' for p in output_parameters):
            output_parameters = (filename_parameter,) + output_parameters
        # remove the last component, since we're going to re-use its name:
        first.components = first.components[:-1]
        # automatically adds the component at the end of the list:
        first.make_instance(fc.name, output_component, fc.at_relative, fc.rotate_relative,
                            output_parameters)

        if input_component is None:
            input_component = 'MCPL_input'
        if input_parameters is None:
            input_parameters = (filename_parameter,)
        elif not any(p.name == 'filename' for p in input_parameters):
            input_parameters = (filename_parameter,) + input_parameters
        if not any(p.name == 'verbose' for p in input_parameters):
            input_parameters = (ComponentParameter('verbose', Expr.float(0)),) + input_parameters
        # the split at component in the second instrument should have already been converted to absolute-positioning:
        sc = second.components[0]
        if sc.at_relative[1] is not None or sc.rotate_relative[1] is not None:
            logger.error("The split-at point should be positioned absolutely in the second instrument")
        # remove the first component before adding an-equal named one:
        second.components = second.components[1:]
        second.make_instance(sc.name, input_component, sc.at_relative, sc.rotate_relative, parameters=input_parameters)
        # move the newly added component to the front of the list:
        second.components = (second.components[-1],) + second.components[:-1]

        return first, second

    def parameter_used(self, name: str):
        """Check that an instrument parameter is used in the instrument"""
        for instance in self.components:
            if instance.parameter_used(name):
                return True
        for section in (self.declare, self.initialize, self.save, self.final):
            for block in section:
                # A more complex check would see if the use itself leads to a parameter being used, but
                # that would be language dependent and probably not worth the effort.
                if name in block:
                    return True
        return False

    def check_instrument_parameters(self, remove=False):
        """Check that all instrument parameters are used in the instrument, and optionally remove any that are not

        Returns
        -------
        int
            The number of unused instrument parameters
        """
        names = [p.name for p in self.parameters]
        used = [self.parameter_used(p.name) for p in self.parameters]
        if not all(used):
            logger.info(f'The following instrument parameters are not used in the instrument: '
                     f'{", ".join([n for n, u in zip(names, used) if not u])}')
            if remove:
                self.parameters = tuple(p for i, p in enumerate(self.parameters) if used[i])
                logger.info(f'Removed unused instrument parameters; {len(self.parameters)} remain')
        return len(used) - sum(used)

    def verify_instance_parameters(self):
        """Check that all instance parameters are of the expected type, and that identifiers which match
        instrument parameter names are flagged as such"""
        for instance in self.components:
            instance.verify_parameters(self.parameters)

    def check_expr(self, expr: int | float | str | Expr):
        if not isinstance(expr, Expr):
            expr = Expr.best(expr)
        # check whether the expression contains any identifiers which are actually InstrumentParameters
        expr.verify_parameters([x.name for x in self.parameters])
        # We then verify that no as-of-yet undefined identifiers exist, but can't in case they're defined in
        # an initalize or share block
        return expr


def _join_raw_tuple(raw_tuple: tuple[RawC, ...]):
    return '\n'.join([str(rc) for rc in raw_tuple])


def _restore_included_components(instr: Instr) -> None:
    """Re-link each included child's components to the top-level instance pool.

    Instances are (de)serialized once, in the top-level Instr; each tree node's
    components are the pool instances whose `source` names something in that
    node's subtree. Order follows the pool, so it is preserved even when
    child-sourced instances are not contiguous.
    """
    pool = instr.components

    def tree_names(node: Instr) -> set:
        names = {node.name}
        for child in node.included:
            names |= tree_names(child)
        return names

    def assign(node: Instr) -> None:
        names = tree_names(node)
        node.components = tuple(x for x in pool if x.source in names)
        for child in node.included:
            assign(child)

    for child in instr.included:
        assign(child)


def _subtract_tuple(parent: tuple, child: tuple, warn: bool) -> tuple:
    """Remove, for each element of `child`, the first ==-equal element of `parent`."""
    remaining = list(parent)
    for item in child:
        try:
            remaining.remove(item)
        except ValueError:
            if warn:
                logger.warning(f'Included content not found in parent during hierarchical write: {item!r}')
    return tuple(remaining)


@lru_cache
def determine_groups(instances) -> dict[str, Group]:
    groups = {}
    for id, inst in enumerate(instances):
        if inst.group:
            if inst.group not in groups:
                groups[inst.group] = Group(inst.group, len(groups))
            groups[inst.group].add(id, inst)
    return groups


# ---------------------------------------------------------------------------
# Helpers for insert_component positioning
# ---------------------------------------------------------------------------

def _orient_is_constant(orient) -> bool:
    """Return True if the Orient's position vector has all numeric (constant) components."""
    if orient is None:
        return False
    try:
        return all(e.has_value for e in orient.position())
    except Exception:
        return False


def _midpoint_at_relative(pred_inst, succ_inst, orientations: dict):
    """Return ``(Vector, reference_instance)`` for the midpoint between *pred_inst* and *succ_inst*.

    If *pred_inst* is ``None``, returns the origin ABSOLUTE.
    If *succ_inst* is ``None``, returns the origin RELATIVE *pred_inst*.
    If both orientations are available and constant, computes the true midpoint
    expressed relative to *pred_inst*; otherwise falls back to the origin of
    *pred_inst*.
    """
    from .orientation import Vector
    from ..common import Expr
    zero = Vector(Expr.float(0), Expr.float(0), Expr.float(0))

    if pred_inst is None:
        return zero, None  # ABSOLUTE origin
    if succ_inst is None:
        return zero, pred_inst

    p_or = orientations.get(pred_inst.name)
    s_or = orientations.get(succ_inst.name)
    if _orient_is_constant(p_or) and _orient_is_constant(s_or):
        p_pos = p_or.position()
        s_pos = s_or.position()
        mid_abs = (p_pos + s_pos) / Expr.float(2.0)
        delta = mid_abs - p_pos
        # Convert global delta to pred's local coordinate frame
        at_in_pred = p_or.rotation('axes') * delta
        return at_in_pred, pred_inst

    # Fallback: place at pred's origin
    return zero, pred_inst


def _downstream_rotate_relative(pred_inst, succ_inst, orientations: dict):
    """Return ``(Angles, reference_instance)`` matching the orientation of the downstream component.

    Expresses the rotation RELATIVE to *pred_inst* when possible (matching the
    convention that AT and ROTATE should share the same reference).  Falls back
    to zero-rotation RELATIVE *pred_inst* (or ABSOLUTE zero if no predecessor).

    The relative rotation is computed as  R_rel = R_succ * R_pred^T  and then
    converted back to Euler angles via :func:`axes_euler_angles`.
    """
    from .orientation import Angles, axes_euler_angles
    from ..common import Expr
    zero = Angles(Expr.float(0), Expr.float(0), Expr.float(0))

    downstream = succ_inst if succ_inst is not None else pred_inst
    if downstream is None:
        return zero, None  # no components at all — ABSOLUTE zero

    if pred_inst is None:
        # No predecessor: use absolute orientation of downstream if available
        d_or = orientations.get(downstream.name)
        if _orient_is_constant(d_or):
            return d_or.angles(), None  # ABSOLUTE
        return zero, None

    # Both pred and succ (or just pred) exist: prefer RELATIVE to pred_inst
    p_or = orientations.get(pred_inst.name)
    if not _orient_is_constant(p_or):
        return zero, pred_inst  # pred orientation unknown — use zero RELATIVE pred

    d_or = orientations.get(downstream.name)
    if downstream is pred_inst or not _orient_is_constant(d_or):
        return zero, pred_inst  # no downstream info — zero RELATIVE pred

    # R_rel = R_succ * R_pred^T  (rotation of succ expressed in pred's frame)
    r_pred = p_or.rotation('axes')
    r_succ = d_or.rotation('axes')
    r_rel = r_succ * r_pred.inverse()
    angles = axes_euler_angles(r_rel, degrees=True)
    return angles, pred_inst


def _normalise_vr(vr, components, vec_cls):
    """Normalise ``(vec_or_tuple, inst_or_str_or_none)`` to ``(vec_cls, Instance | None)``.

    Converts a plain tuple like ``((0, 0, 1), 'comp_name')`` to
    ``(Vector(0, 0, 1), Instance)``.
    """
    from ..common import Expr
    if vr is None:
        return vr
    vec, ref = vr
    if isinstance(vec, (tuple, list)):
        vec = vec_cls(*[Expr.best(v) for v in vec])
    if isinstance(ref, str):
        ref = next((c for c in components if c.name == ref), None)
    return vec, ref


def _fix_forward_ref(at_relative, insert_idx, pred_inst, orientations: dict):
    """Re-express *at_relative* relative to *pred_inst* if its reference comes after *insert_idx*.

    If the reference component's index >= *insert_idx* (i.e., it will come
    *after* the new instance), the position is converted to be expressed
    relative to *pred_inst* using absolute coordinate arithmetic.  If the
    required orientations are unavailable, a ``RuntimeError`` is raised.
    """
    if at_relative is None:
        return at_relative
    at_vec, ref_inst = at_relative
    if ref_inst is None or pred_inst is None:
        return at_relative  # ABSOLUTE or no predecessor — nothing to fix

    if ref_inst is pred_inst:
        return at_relative  # already relative to pred — nothing to do

    ref_or = orientations.get(ref_inst.name)
    pred_or = orientations.get(pred_inst.name)
    if not _orient_is_constant(ref_or) or not _orient_is_constant(pred_or):
        raise RuntimeError(
            f"Cannot re-express position relative to {pred_inst.name!r}: "
            f"orientations of {ref_inst.name!r} or {pred_inst.name!r} are unavailable or non-constant."
        )

    # abs_pos = ref_pos + ref_rotation_coordinates @ at_vec
    abs_pos = ref_or.position() + ref_or.rotation('coordinates') * at_vec
    delta = abs_pos - pred_or.position()
    at_in_pred = pred_or.rotation('axes') * delta
    return at_in_pred, pred_inst


def _fix_forward_ref_rotation(rotate_relative, insert_idx, pred_inst, orientations: dict):
    """Re-express *rotate_relative* RELATIVE to *pred_inst* if its reference is forward.

    Computes the absolute rotation of the reference and then expresses it
    relative to *pred_inst* using  R_rel = R_ref_composed * R_pred^T,
    keeping the same reference as AT so McCode sees a consistent pair.
    """
    if rotate_relative is None:
        return rotate_relative
    angles, ref_inst = rotate_relative
    if ref_inst is None or pred_inst is None:
        return rotate_relative  # ABSOLUTE or no predecessor

    if ref_inst is pred_inst:
        return rotate_relative

    ref_or = orientations.get(ref_inst.name)
    pred_or = orientations.get(pred_inst.name)
    if not _orient_is_constant(ref_or) or not _orient_is_constant(pred_or):
        raise RuntimeError(
            f"Cannot re-express rotation relative to predecessor: "
            f"orientation of {ref_inst.name!r} or {pred_inst.name!r} is unavailable or non-constant."
        )

    from .orientation import axes_euler_angles, Rotation
    # Absolute rotation of the original (ref + angles)
    r_angles = Rotation.from_angles(angles)
    r_abs = r_angles * ref_or.rotation('axes')
    # Express relative to pred_inst
    r_rel = r_abs * pred_or.rotation('axes').inverse()
    rel_angles = axes_euler_angles(r_rel, degrees=True)
    return rel_angles, pred_inst
