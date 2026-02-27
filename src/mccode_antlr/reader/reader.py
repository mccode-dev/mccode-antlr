from __future__ import annotations
from pathlib import Path
from loguru import logger
from msgspec import Struct, field

from .registry import Registry, registries_match, registry_from_specification
from ..comp import Comp
from ..common import Mode

from mccode_antlr import Flavor


# ---------------------------------------------------------------------------
# Process-level in-memory + disk component cache
# ---------------------------------------------------------------------------

class _ComponentCache:
    """Singleton two-level cache for parsed :class:`~mccode_antlr.comp.Comp` objects.

    **Level 1 – in-memory dict** (per process):
    Maps absolute ``.comp`` path → ``(mtime_ns, Comp)``.  Hits cost nothing
    beyond a dict lookup and a ``stat()`` call.

    **Level 2 – disk JSON cache** (persists across process restarts):
    A ``{name}.comp.json`` file is written alongside every ``.comp`` file the
    first time it is parsed.  On subsequent loads the JSON is decoded by
    :func:`mccode_antlr.io.json.from_json` in ~0.1 ms instead of running the
    ANTLR parser (~10–25 ms per component).  The JSON file's mtime is compared
    to the ``.comp`` file's mtime; a stale JSON is discarded and the component
    is re-parsed.  If the cache directory is not writable the disk level is
    silently skipped.

    Use :meth:`clear` to flush in-memory entries (disk files are left intact
    and will be reloaded on the next access).
    """
    _instance: '_ComponentCache | None' = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._store: dict[str, tuple[int, Comp]] = {}
            cls._instance._source_overrides: dict[str, str] = {}
        return cls._instance

    @staticmethod
    def _json_path(comp_path: Path) -> Path:
        return comp_path.with_suffix(comp_path.suffix + '.json')

    def get(self, path: Path) -> Comp | None:
        key = str(path)
        try:
            comp_mtime = path.stat().st_mtime_ns
        except OSError:
            return None

        # Level 1: in-memory
        if key in self._store:
            cached_mtime, comp = self._store[key]
            if cached_mtime == comp_mtime:
                return comp
            del self._store[key]

        # Level 2: disk JSON
        json_path = self._json_path(path)
        try:
            if json_path.exists() and json_path.stat().st_mtime_ns >= comp_mtime:
                from mccode_antlr.io.json import from_json
                comp = from_json(json_path.read_bytes())
                if isinstance(comp, Comp):
                    self._store[key] = (comp_mtime, comp)
                    return comp
        except Exception:
            pass  # corrupt or unreadable JSON — fall through to ANTLR parse

        return None

    def put(self, path: Path, comp: Comp) -> None:
        try:
            mtime = path.stat().st_mtime_ns
            self._store[str(path)] = (mtime, comp)
        except OSError:
            return
        # Write disk JSON cache alongside the .comp file (best-effort)
        json_path = self._json_path(path)
        try:
            from mccode_antlr.io.json import to_json
            json_path.write_bytes(to_json(comp))
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

def make_reader_error_listener(super_class, filetype, name, source, pre=5, post=2):
    class ReaderErrorListener(super_class):
        def __init__(self):
            self.filetype = filetype
            self.name = name
            self.source = source
            self.pre = pre
            self.post = post

        def syntaxError(self, recognizer, offendingSymbol, *args, **kwargs):
            if len(args) == 4 and isinstance(args[3], str):
                # The 'speedy-antlr' syntax
                char_index, line, column, msg = args
            else:
                # the antlr4 (4.13.0) syntax
                line, column, msg, e = args
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

    def locate(self, name: str, which: str = None, ext: str = None, strict: bool = False):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        for reg in registries:
            if reg.known(name, ext, strict=strict):
                return reg.path(name, ext)
        names = [reg.name for reg in registries]
        msg = "registry " + names[0] if len(names) == 1 else 'registries: ' + ','.join(names)
        raise RuntimeError(f'{name} not found in {msg}')

    def contents(self, name: str, which: str = None, ext: str = None, strict: bool = False):
        # Return in-memory override (unsaved LSP edits) when available.
        if ext in (None, '.comp'):
            override = component_cache.get_override(name)
            if override is not None:
                return override
        registries = self.registries if which is None else [x for x in self.registries
                                                            if x.name in which]
        for reg in registries:
            if reg.known(name, ext, strict=strict):
                return reg.contents(name, ext)
        names = [reg.name for reg in registries]
        msg = "registry " + names[0] if len(names) == 1 else 'registries: ' + ','.join(
            names)
        raise RuntimeError(f'{name} not found in {msg}')

    def fullname(self, name: str, which: str = None, ext: str=None, strict: bool = False):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        for reg in registries:
            if reg.known(name, ext, strict=strict):
                return reg.fullname(name, ext)
        names = [reg.name for reg in registries]
        msg = "registry " + names[0] if len(names) == 1 else 'registries: ' + ','.join(names)
        raise RuntimeError(f'{name} not found in {msg}')

    def known(self, name: str, which: str = None, strict: bool = False):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        return any([reg.known(name, strict=strict) for reg in registries])

    def unique(self, name: str, which: str = None):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        return sum([1 for reg in registries if reg.unique(name)]) == 1

    def contain(self, name: str, which: str = None, strict: bool = False):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        return [reg.name for reg in registries if reg.known(name, strict=strict)]

    def stream(self, name: str, which: str = None, strict: bool = False):
        from antlr4 import InputStream
        return InputStream(self.contents(name, which=which, strict=strict))

    def add_component(self, name: str, current_instance_name=None):
        if name in self.components:
            raise RuntimeError("The named component is already known.")
        from ..grammar import McComp_ErrorListener

        filename = str(self.locate(name, ext='.comp', strict=True))
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
            res = Comp.from_source(
                self, error_listener, source, filename, fullname
            )
            component_cache.put(abs_path, res)

        self.components[name] = res

    def get_component(self, name: str, current_instance_name=None):
        if name not in self.components:
            self.add_component(name, current_instance_name=current_instance_name)
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

    def evict(self, name: str) -> None:
        """Remove *name* from ``self.components`` and the source-override dict.

        The next ``get_component`` call will re-read from the process-level cache
        (which uses mtime) or re-parse from disk — useful after a file save.
        """
        self.components.pop(name, None)
        component_cache.clear_override(name)

    def get_instrument(self, name: str | None | Path, destination=None, mode: Mode | None = None):
        """Load and parse an instr Instrument definition file

        In McCode3 fashion, the instrument file *should* be in the current working directory.
        In new-fashion, the registry/registries will be checked if it is not.
        """
        from antlr4 import InputStream
        from ..grammar import McInstr_parse, McInstr_ErrorListener
        from ..instr import InstrVisitor, Instr
        path = name if isinstance(name, Path) else Path(name)
        if path.suffix != '.instr':
            path = path.with_suffix(f'{path.suffix}.instr')
        if path.exists() and path.is_file():
            source = path.read_text()
        else:
            path = self.locate(path.name)  # include the .instr for the search
            source = self.contents(path.name)

        if not path.resolve().exists():
            filename = name
        else:
            filename = path.resolve().as_posix()

        stream = InputStream(source)
        error_listener = make_reader_error_listener(
            McInstr_ErrorListener, 'Instrument', name, source
        )
        tree = McInstr_parse(stream, 'prog', error_listener)

        visitor = InstrVisitor(self, filename, destination=destination, mode=mode)
        res = visitor.visitProg(tree)
        if not isinstance(res, Instr):
            raise RuntimeError(f'Parsing instrument file {filename} did not produce an Instr object')
        res.source = filename
        res.registries = tuple(self.registries)
        return res
