from __future__ import annotations
import os
import re
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
import msgspec
from msgspec import Raw, Struct, field

from .registry import (Registry, registries_match, registry_from_specification,
                       resolve_from_registries, origin_label)
from ..comp import Comp

from mccode_antlr import Flavor
from mccode_antlr.utils import McCodeSyntaxError

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Process-level in-memory + disk component cache
# ---------------------------------------------------------------------------

# Bump when a change to the component parser/visitor or to the serialised Comp
# schema means a JSON sidecar written by an older mccode-antlr can no longer be
# trusted (e.g. the #321 INHERIT block-override fix). Combined with the package
# version into the sidecar filename, so an upgrade -- or a working-tree change
# during development -- transparently re-parses the .comp file exactly once.
# 3: .comp files are decoded as UTF-8, not the locale encoding (#364), so
#    sidecars parsed on e.g. a cp1252 Windows system may hold garbled text.
# 4: that decoding also kept CRLF line endings, so sidecars parsed from a CRLF
#    checkout hold carriage returns in their C blocks.
# 5: sidecars record the mtime of every source file the Comp was built from
#    (INHERIT/COPY parents included), as {"sources": {...}, "ir": <Comp>}.
_COMPONENT_CACHE_FORMAT = 5


@lru_cache(maxsize=1)
def _component_cache_salt() -> str:
    from hashlib import sha1
    from mccode_antlr.version import version
    return sha1(f'{_COMPONENT_CACHE_FORMAT}:{version()}'.encode()).hexdigest()[:12]


# Sources (path -> mtime_ns) of the components resolved while each in-progress
# parse runs; innermost parse last.  A `DEFINE COMPONENT b INHERIT a` reaches
# `a` through Reader.get_component, which records it here, so b's cache entry
# goes stale when a's file changes, not only when b's does.
# ponytail: process-global, so concurrent parses in threads would mix their
# dependencies; make it a ContextVar if Readers ever parse in parallel threads.
_dependency_frames: list[dict[str, int]] = []


@contextmanager
def recording_dependencies():
    """Collect the sources of every component resolved inside the block."""
    frame: dict[str, int] = {}
    _dependency_frames.append(frame)
    try:
        yield frame
    finally:
        _dependency_frames.pop()


def _note_dependency(path: Path) -> None:
    if not _dependency_frames:
        return
    sources = component_cache.sources(path)
    if sources is None:  # in-memory level flushed since it was parsed
        try:
            sources = {str(path): path.stat().st_mtime_ns}
        except OSError:
            return
    _dependency_frames[-1].update(sources)


def _sources_are_current(sources: dict[str, int]) -> bool:
    try:
        return all(Path(p).stat().st_mtime_ns == m for p, m in sources.items())
    except OSError:
        return False


class _Sidecar(Struct):
    sources: dict[str, int]  # relative to the sidecar's directory where possible
    ir: Raw


def _read_sidecar(json_path: Path) -> tuple[dict[str, int], Raw] | None:
    """The sidecar's sources (made absolute) and raw Comp JSON, if it is current."""
    try:
        sidecar = msgspec.json.decode(json_path.read_bytes(), type=_Sidecar)
    except Exception:
        return None  # missing, corrupt, or an older layout
    sources = {str(json_path.parent / p): m for p, m in sidecar.sources.items()}
    return (sources, sidecar.ir) if _sources_are_current(sources) else None


def _relative_sources(sources: dict[str, int], directory: Path) -> dict[str, int]:
    """Relative paths keep a sidecar valid when its whole tree is copied (cp -a)."""
    def rel(p):
        try:
            return os.path.relpath(p, directory)
        except ValueError:  # different drive on Windows
            return p
    return {rel(p): m for p, m in sources.items()}


def component_ir_enabled() -> bool:
    """Whether component IR sidecars are read and written (``cache.component_ir``)."""
    from mccode_antlr.config import config
    value = config['cache']['component_ir'].get()
    if isinstance(value, str):  # `mccode-antlr config set` stores the text it is given
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)


class _ComponentCache:
    """Singleton two-level cache for parsed :class:`~mccode_antlr.comp.Comp` objects.

    **Level 1 – in-memory dict** (per process):
    Maps absolute ``.comp`` path → ``(sources, Comp)``, where *sources* maps
    every file the Comp was built from -- itself and any INHERIT/COPY parents,
    transitively -- to its mtime.  A hit costs a dict lookup and one ``stat()``
    per source.

    **Level 2 – disk JSON cache** (persists across process restarts; only when
    the ``cache.component_ir`` configuration value is true):
    A ``{name}.comp.<salt>.json`` file is written alongside every ``.comp`` file
    the first time it is parsed.  On subsequent loads the JSON is decoded by
    :func:`mccode_antlr.io.json.from_json` in ~0.1 ms instead of running the
    ANTLR parser (~10–25 ms per component).  The JSON records the same
    *sources* mtimes; if any differs the JSON is ignored and the component is
    re-parsed.  The ``<salt>`` encodes the mccode-antlr version and an
    internal cache-format number (:data:`_COMPONENT_CACHE_FORMAT`), so sidecars
    written by a different build are ignored and pruned rather than trusted.
    If the cache directory is not writable the disk level is silently skipped.

    Use :meth:`clear` to flush in-memory entries (disk files are left intact
    and will be reloaded on the next access).
    """
    _instance: '_ComponentCache | None' = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._store: dict[str, tuple[dict[str, int], Comp]] = {}
            cls._instance._source_overrides: dict[str, str] = {}
        return cls._instance

    @staticmethod
    def _json_path(comp_path: Path) -> Path:
        return comp_path.with_suffix(comp_path.suffix + f'.{_component_cache_salt()}.json')

    @staticmethod
    def _foreign_json_paths(comp_path: Path):
        """Sidecars for *comp_path* written by another build -- the pre-salt
        ``{name}.comp.json`` or a ``{name}.comp.<other-salt>.json`` -- which must
        not be trusted and should be pruned."""
        keep = _ComponentCache._json_path(comp_path).name
        stem = comp_path.name  # e.g. 'Foo.comp'
        try:
            candidates = list(comp_path.parent.glob(stem + '*.json'))
        except OSError:
            return
        for p in candidates:
            if p.name == keep:
                continue
            trailing = p.name[len(stem):]  # '.json' or '.<salt>.json'
            if re.fullmatch(r'(\.[0-9a-f]{12})?\.json', trailing):
                yield p

    def get(self, path: Path) -> Comp | None:
        key = str(path)

        # Level 1: in-memory
        if key in self._store:
            sources, comp = self._store[key]
            if _sources_are_current(sources):
                return comp
            del self._store[key]

        # Level 2: disk JSON
        if component_ir_enabled() and (found := _read_sidecar(self._json_path(path))) is not None:
            sources, ir = found
            try:
                from mccode_antlr.io.json import from_json
                comp = from_json(bytes(ir))
            except Exception:
                return None  # corrupt JSON — fall through to ANTLR parse
            if isinstance(comp, Comp):
                self._store[key] = (sources, comp)
                return comp

        return None

    def sources(self, path: Path) -> dict[str, int] | None:
        """The files (path -> mtime_ns) the in-memory entry for *path* was built from."""
        entry = self._store.get(str(path))
        return None if entry is None else entry[0]

    def put(self, path: Path, comp: Comp, depends: dict[str, int] | None = None) -> None:
        """Cache *comp*, parsed from *path* using the components in *depends*
        (as collected by :func:`recording_dependencies`)."""
        try:
            sources = {str(path): path.stat().st_mtime_ns, **(depends or {})}
            self._store[str(path)] = (sources, comp)
        except OSError:
            return
        if not component_ir_enabled():
            return
        # Write disk JSON cache alongside the .comp file (best-effort)
        json_path = self._json_path(path)
        try:
            from mccode_antlr.io.json import to_json
            json_path.write_bytes(msgspec.json.encode(_Sidecar(
                sources=_relative_sources(sources, json_path.parent),
                ir=Raw(to_json(comp)),
            )))
            for stale in self._foreign_json_paths(path):
                stale.unlink(missing_ok=True)
        except Exception:
            pass

    def evict(self, path: Path) -> None:
        """Remove a single path from the in-memory store (disk JSON is preserved)."""
        self._store.pop(str(path), None)

    # ------------------------------------------------------------------
    # In-memory source overrides (for LSP-provided unsaved edits)
    # ------------------------------------------------------------------

    def override_source(self, name: str, source: str) -> None:
        """Store *source* as the in-memory text for component *name*.

        ``Reader.contents()`` checks this dict before reading from disk,
        so all readers will see the live text immediately.
        """
        self._source_overrides[name] = source

    def clear_override(self, name: str) -> None:
        """Remove the in-memory source override for *name*."""
        self._source_overrides.pop(name, None)

    def get_override(self, name: str) -> str | None:
        return self._source_overrides.get(name)

    def clear(self) -> None:
        """Flush all in-memory entries (disk JSON files are preserved)."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


component_cache = _ComponentCache()


# Any component IR sidecar: this build's `{name}.comp.<salt>.json`, another
# build's, or the pre-salt `{name}.comp.json`.
_COMPONENT_IR_SUFFIX_RE = re.compile(r'\.comp(?:\.[0-9a-f]{12})?\.json\Z')


def component_ir_path(comp_path: Path) -> Path:
    """The IR-cache JSON sidecar path *this build* reads and writes for *comp_path*."""
    return _ComponentCache._json_path(comp_path)


def component_ir_comp_path(json_path: Path) -> Path:
    """The ``.comp`` file an IR sidecar belongs to (inverse of :func:`component_ir_path`)."""
    return json_path.with_name(_COMPONENT_IR_SUFFIX_RE.sub('.comp', json_path.name))


def is_component_ir_sidecar(path) -> bool:
    """True for any component IR sidecar, whichever build wrote it.

    Accepts a :class:`~pathlib.Path` or a bare filename. Used to keep generated
    sidecars out of places that should only ever describe source files -- see
    :func:`mccode_antlr.cli.cache.build_registry`.
    """
    name = path.name if isinstance(path, Path) else str(path)
    return _COMPONENT_IR_SUFFIX_RE.search(name) is not None


def iter_component_ir_paths(root: Path):
    """Every component IR sidecar under *root*, regardless of which build wrote it."""
    for path in root.rglob('*.comp*.json'):
        if is_component_ir_sidecar(path):
            yield path


def component_ir_is_fresh(json_path: Path) -> bool:
    """True when this build wrote *json_path* and none of its sources has changed."""
    return component_ir_is_current(json_path) and _read_sidecar(json_path) is not None


def component_ir_is_current(json_path: Path) -> bool:
    """True when *json_path* is the sidecar name this build would write (right salt)."""
    return json_path.name == component_ir_path(component_ir_comp_path(json_path)).name


def make_reader_error_listener(super_class, filetype, name, source, pre=5, post=2):
    class ReaderErrorListener(super_class):
        def __init__(self):
            self.filetype = filetype
            self.name = name
            self.source = source
            self.pre = pre
            self.post = post
            self.errors = []

        def raise_for_errors(self):
            """Raise if the parse reported any syntax error.

            Called after parsing rather than from syntaxError itself, so that
            ANTLR's recovery can report every error in the file before the first
            one aborts it.
            """
            if self.errors:
                raise McCodeSyntaxError(self.filetype, self.name, self.errors)

        def syntaxError(self, recognizer, offendingSymbol, *args, **kwargs):
            if len(args) == 4 and isinstance(args[3], str):
                # The 'speedy-antlr' syntax
                char_index, line, column, msg = args
            else:
                # the antlr4 (4.13.0) syntax
                line, column, msg, e = args
            self.errors.append((line, column, msg))
            logger.error(f'Syntax error in parsing {self.filetype} {self.name} at {line},{column}')
            lines = self.source.split('\n')
            pre_lines = lines[line-self.pre:line]
            post_lines = lines[line:line+self.post]
            for line in pre_lines:
                logger.info(line)
            logger.error('~'*column + '^ ' + msg)
            for line in post_lines:
                logger.info(line)

    return ReaderErrorListener()


class Reader(Struct):
    registries: list[Registry] = field(default_factory=list)
    components: dict[str, Comp] = field(default_factory=dict)
    flavor: Flavor | None = None
    # The resolved .comp file of each component in `components` read from disk.
    component_paths: dict[str, Path] = field(default_factory=dict)

    def __hash__(self):
        return hash((tuple(self.registries), tuple(self.components.items()), self.flavor))

    def __post_init__(self):
        from .registry import ordered_registries, default_registries
        if self.flavor is None:
            self.flavor = Flavor.MCSTAS
        if len(self.registries) == 0:
            self.registries = default_registries(self.flavor)
        self.registries = list(ordered_registries(self.registries))

    def prepend_registry(self, reg: Registry):
        self.registries[:0] = [reg, ]

    def append_registry(self, reg: Registry):
        self.registries.append(reg)

    def handle_search_keyword(self, spec: str):
        if not any(registries_match(reg, spec) for reg in self.registries):
            reg = registry_from_specification(spec)
            if reg is not None:
                self.prepend_registry(reg)
            else:
                raise RuntimeError(f"Registry specification {spec} did not specify a valid registry!")

    def _candidates(self, which: str = None):
        return self.registries if which is None else [x for x in self.registries if x.name in which]

    def _first_resolved(self, action, name: str, which: str = None, ext: str = None,
                        strict: bool = False):
        return resolve_from_registries(self._candidates(which), name, action, ext, strict)

    def locate(self, name: str, which: str = None, ext: str = None, strict: bool = False):
        return self._first_resolved(lambda reg: reg.path(name, ext), name, which, ext, strict)

    def contents(self, name: str, which: str = None, ext: str = None, strict: bool = False):
        # Return in-memory override (unsaved LSP edits) when available.
        if ext in (None, '.comp'):
            override = component_cache.get_override(name)
            if override is not None:
                return override
        return self._first_resolved(lambda reg: reg.contents(name, ext), name, which, ext, strict)

    def fullname(self, name: str, which: str = None, ext: str=None, strict: bool = False):
        return self._first_resolved(lambda reg: reg.fullname(name, ext), name, which, ext, strict)

    def known(self, name: str, which: str = None, strict: bool = False):
        registries = self._candidates(which)
        return any([reg.known(name, strict=strict) for reg in registries])

    def unique(self, name: str, which: str = None):
        registries = self._candidates(which)
        return sum([1 for reg in registries if reg.unique(name)]) == 1

    def contain(self, name: str, which: str = None, strict: bool = False):
        registries = self._candidates(which)
        return [reg.name for reg in registries if reg.known(name, strict=strict)]

    def stream(self, name: str, which: str = None, strict: bool = False):
        from antlr4 import InputStream
        return InputStream(self.contents(name, which=which, strict=strict))

    def add_component(self, name: str, current_instance_name=None):
        if name in self.components:
            raise RuntimeError("The named component is already known.")
        from ..grammar import McComp_ErrorListener

        ext = '.comp'
        path, reg = resolve_from_registries(
            self._candidates(), name, lambda r: (r.path(name, ext), r), ext, True,
        )
        filename = str(path)
        abs_path = Path(filename).resolve()

        # Check the process-level cache before running the ANTLR parser.
        if (res := component_cache.get(abs_path)) is not None:
            logger.debug(f'Component cache hit: {abs_path}')
        else:
            source = self.contents(name, ext='.comp', strict=True)
            fullname = self.fullname(name, ext='.comp', strict=True)
            error_listener = make_reader_error_listener(
                McComp_ErrorListener,'Component', name, source
            )
            with recording_dependencies() as depends:
                res = Comp.from_source(
                    self, error_listener, source, filename, fullname
                )
            component_cache.put(abs_path, res, depends)
        self.component_paths[name] = abs_path
        # Reflect *this* resolution's registry even on a cache hit -- the cache
        # is keyed by filesystem path, not by registry, so in principle a
        # different registry could resolve the same abs_path for another Reader.
        res.origin = origin_label(reg)

        self.components[name] = res

    def get_component(self, name: str, current_instance_name=None):
        if name not in self.components:
            self.add_component(name, current_instance_name=current_instance_name)
        if name in self.component_paths:  # not for an inject_source'd component
            _note_dependency(self.component_paths[name])
        return self.components[name]

    def inject_source(self, name: str, source: str, filename: str | None = None) -> None:
        """Parse *source* as a component definition and store it in ``self.components``.

        Bypasses all file-based caches (process-level and disk JSON) so that
        unsaved in-memory edits are immediately reflected in hover/completion.
        Also stores *source* in the process-level cache's source-override dict so
        that ``contents()`` returns the live text for all Reader instances.

        Raises nothing on parse failure — the existing cached component is kept.
        """
        from ..grammar import McComp_ErrorListener
        error_listener = make_reader_error_listener(
            McComp_ErrorListener, 'Component', name, source
        )
        try:
            res = Comp.from_source(self, error_listener, source, filename)
        except Exception:
            return
        if not isinstance(res, Comp):
            return
        component_cache.override_source(name, source)
        self.components[name] = res
        self.component_paths.pop(name, None)

    def evict(self, name: str) -> None:
        """Remove *name* from ``self.components`` and the source-override dict.

        The next ``get_component`` call will re-read from the process-level cache
        (which uses mtime) or re-parse from disk — useful after a file save.
        """
        self.components.pop(name, None)
        self.component_paths.pop(name, None)
        component_cache.clear_override(name)

    def get_instrument(self, name: str | None | Path, destination=None):
        """Load and parse an instr Instrument definition file

        In McCode3 fashion, the instrument file *should* be in the current working directory.
        In new-fashion, the registry/registries will be checked if it is not.

        `destination` is the InstrVisitor of the *including* instrument when this file
        is the target of a TRACE %include, or None at the top level.
        """
        from antlr4 import InputStream
        from ..grammar import McInstr_parse, McInstr_ErrorListener
        from ..instr import InstrVisitor, Instr
        path = name if isinstance(name, Path) else Path(name)
        if path.suffix not in ('', '.instr'):
            raise RuntimeError(
                f"%include of {str(name)!r} is not supported: mccode-antlr's %include always "
                f"parses its target as an .instr instrument definition, so a suffix other than "
                f".instr or no suffix (implying .instr) can never resolve. Some McStas-3 "
                f"instruments abuse %include to splice raw file contents (e.g. generated C "
                f"fragments) into DECLARE/INITIALIZE/TRACE sections; that pattern is not "
                f"supported here and would need restructuring (e.g. moving the generated code "
                f"into a real .instr/.comp, or embedding it directly) to translate with mccode-antlr."
            )
        if path.suffix != '.instr':
            path = path.with_suffix(f'{path.suffix}.instr')
        if path.exists() and path.is_file():
            from mccode_antlr.common.encoding import read_source_text
            source = read_source_text(path)
        else:
            path = self.locate(path.name)  # include the .instr for the search
            source = self.contents(path.name)

        if not path.resolve().exists():
            filename = name
        else:
            filename = path.resolve().as_posix()

        chain = []
        scope = destination
        while scope is not None:
            chain.append(scope.filename)
            scope = scope.destination
        if filename in chain:
            raise RuntimeError(
                f'%include cycle detected while parsing {filename!r}: '
                f'include chain {" -> ".join(reversed(chain))} -> {filename}'
            )

        stream = InputStream(source)
        error_listener = make_reader_error_listener(
            McInstr_ErrorListener, 'Instrument', name, source
        )
        tree = McInstr_parse(stream, 'prog', error_listener)
        error_listener.raise_for_errors()

        visitor = InstrVisitor(self, filename, destination=destination)
        res = visitor.visitProg(tree)
        if not isinstance(res, Instr):
            raise RuntimeError(f'Parsing instrument file {filename} did not produce an Instr object')
        res.source = filename
        res.registries = tuple(self.registries)
        return res
