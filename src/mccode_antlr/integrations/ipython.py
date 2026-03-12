from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mccode_antlr.assembler import Assembler
from mccode_antlr.run import Simulation

from ._python_completion import (
    CompletionCandidate,
    get_component_instance_names,
    get_component_names,
    get_component_parameters,
    get_instrument_parameters,
    get_runtime_keywords,
)

if TYPE_CHECKING:
    from IPython.core.completer import CompletionContext, SimpleMatcherResult


_CALL_RE = re.compile(r'(?P<object>[A-Za-z_][A-Za-z0-9_]*)\.(?P<method>component|run|scan)\(')


def _require_ipython():
    try:
        from IPython import get_ipython
        from IPython.core.completer import SimpleCompletion
    except ImportError as exc:
        raise ImportError(
            'Install mccode_antlr[ipython] to use the IPython matcher integration.'
        ) from exc
    return get_ipython, SimpleCompletion


@dataclass(frozen=True)
class _CallContext:
    object_name: str
    method: str
    args_prefix: str


def _no_match() -> dict:
    return {'completions': [], 'suppress': False}


def _scan_nesting(text: str, *, initial_paren: int = 0, initial_brace: int = 0) -> tuple[int, int]:
    paren = initial_paren
    brace = initial_brace
    bracket = 0
    quote: str | None = None
    escape = False

    for char in text:
        if quote is not None:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == quote:
                quote = None
            continue

        if char in {'"', "'"}:
            quote = char
        elif char == '(':
            paren += 1
        elif char == ')':
            paren -= 1
        elif char == '{':
            brace += 1
        elif char == '}':
            brace -= 1
        elif char == '[':
            bracket += 1
        elif char == ']':
            bracket -= 1

    return paren, brace


def _find_open_call(prefix: str) -> _CallContext | None:
    matches = list(_CALL_RE.finditer(prefix))
    for match in reversed(matches):
        args_prefix = prefix[match.end():]
        paren, _ = _scan_nesting(args_prefix, initial_paren=1)
        if paren > 0:
            return _CallContext(match.group('object'), match.group('method'), args_prefix)
    return None


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    paren = brace = bracket = 0
    quote: str | None = None
    escape = False

    for index, char in enumerate(text):
        if quote is not None:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == quote:
                quote = None
            continue

        if char in {'"', "'"}:
            quote = char
        elif char == '(':
            paren += 1
        elif char == ')':
            paren -= 1
        elif char == '{':
            brace += 1
        elif char == '}':
            brace -= 1
        elif char == '[':
            bracket += 1
        elif char == ']':
            bracket -= 1
        elif char == ',' and paren == 0 and brace == 0 and bracket == 0:
            parts.append(text[start:index])
            start = index + 1

    parts.append(text[start:])
    return parts


def _string_value(segment: str) -> str | None:
    text = segment.strip()
    if not text or text[0] not in {'"', "'"}:
        return None

    quote = text[0]
    escape = False
    chars: list[str] = []
    for char in text[1:]:
        if escape:
            chars.append(char)
            escape = False
        elif char == '\\':
            escape = True
        elif char == quote:
            return ''.join(chars)
        else:
            chars.append(char)
    return ''.join(chars)


def _current_string_fragment(segment: str) -> str | None:
    quote: str | None = None
    escape = False
    start = 0
    for index, char in enumerate(segment):
        if quote is not None:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            start = index + 1
    if quote is None:
        return None
    return segment[start:]


def _top_level_contains(text: str, needle: str) -> bool:
    paren = brace = bracket = 0
    quote: str | None = None
    escape = False
    for char in text:
        if quote is not None:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == '(':
            paren += 1
        elif char == ')':
            paren -= 1
        elif char == '{':
            brace += 1
        elif char == '}':
            brace -= 1
        elif char == '[':
            bracket += 1
        elif char == ']':
            bracket -= 1
        elif char == needle and paren == 0 and brace == 0 and bracket == 0:
            return True
    return False


def _component_type_name(args_prefix: str) -> str | None:
    for segment in _split_top_level(args_prefix):
        stripped = segment.strip()
        if stripped.startswith('type_name'):
            _, _, value = stripped.partition('=')
            return _string_value(value)

    segments = _split_top_level(args_prefix)
    if len(segments) >= 2:
        return _string_value(segments[1])
    return None


def _component_type_fragment(args_prefix: str) -> str | None:
    segments = _split_top_level(args_prefix)
    if not segments:
        return None

    current = segments[-1]
    stripped = current.strip()
    if stripped.startswith('type_name'):
        _, _, value = stripped.partition('=')
        return _current_string_fragment(value)
    if len(segments) == 2:
        return _current_string_fragment(current)
    return None


def _keyword_dict_fragment(args_prefix: str, keyword: str) -> str | None:
    pattern = re.compile(rf'\b{re.escape(keyword)}\s*=\s*\{{')
    matches = list(pattern.finditer(args_prefix))
    for match in reversed(matches):
        fragment = args_prefix[match.end():]
        _, brace = _scan_nesting(fragment, initial_brace=1)
        if brace > 0:
            return fragment
    return None


def _leading_dict_fragment(args_prefix: str) -> str | None:
    stripped = args_prefix.lstrip()
    if not stripped.startswith('{'):
        return None
    fragment = stripped[1:]
    _, brace = _scan_nesting(fragment, initial_brace=1)
    return fragment if brace > 0 else None


def _dict_key_fragment(dict_fragment: str) -> str | None:
    segments = _split_top_level(dict_fragment)
    current = segments[-1] if segments else dict_fragment
    if _top_level_contains(current, ':'):
        return None
    return _current_string_fragment(current)


def _bare_identifier_fragment(segment: str) -> str | None:
    stripped = segment.strip()
    if not stripped or '=' in stripped or any(ch in stripped for ch in '{}[]:'):
        return None
    match = re.search(r'[A-Za-z_][A-Za-z0-9_]*$', stripped)
    return match.group(0) if match else None


def _keyword_value(args_prefix: str, keyword: str) -> str | None:
    for segment in _split_top_level(args_prefix):
        stripped = segment.strip()
        if stripped.startswith(keyword):
            name, sep, value = stripped.partition('=')
            if sep and name.strip() == keyword:
                return value
    return None


def _positional_value(args_prefix: str, index: int) -> str | None:
    segments = _split_top_level(args_prefix)
    if len(segments) <= index:
        return None
    stripped = segments[index].strip()
    if not stripped or '=' in stripped:
        return None
    return segments[index]


def _reference_fragment_from_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped[0] not in {'(', '['}:
        return None
    inner = stripped[1:]
    segments = _split_top_level(inner)
    if len(segments) < 2:
        return None
    return _current_string_fragment(segments[1])


def _relative_reference_fragment(args_prefix: str) -> str | None:
    for keyword, position in (('at', 2), ('rotate', 3)):
        fragment = _reference_fragment_from_value(_keyword_value(args_prefix, keyword))
        if fragment is not None:
            return fragment
        fragment = _reference_fragment_from_value(_positional_value(args_prefix, position))
        if fragment is not None:
            return fragment
    return None


def _candidate_result(candidates: list[CompletionCandidate], prefix: str, *, ordered: bool = True) -> dict:
    _, SimpleCompletion = _require_ipython()
    filtered = [
        SimpleCompletion((candidate.insert_text or candidate.label), type=candidate.kind)
        for candidate in candidates
        if not prefix or candidate.label.startswith(prefix)
    ]
    return {
        'completions': filtered,
        'matched_fragment': prefix,
        'ordered': ordered,
        'suppress': False,
    }


class McCodeIPythonMatcher:
    """IPython matcher for mccode_antlr Assembler and Simulation authoring."""

    matcher_api_version = 2
    matcher_identifier = 'mccode_antlr.ipython'
    matcher_priority = 50

    def __init__(self, shell=None):
        self.shell = shell
        self.__qualname__ = self.__class__.__qualname__

    def _shell(self):
        if self.shell is not None:
            return self.shell
        get_ipython, _ = _require_ipython()
        return get_ipython()

    def _resolve_object(self, name: str):
        shell = self._shell()
        if shell is None:
            return None
        for namespace_name in ('user_ns', 'user_global_ns'):
            namespace = getattr(shell, namespace_name, None)
            if isinstance(namespace, dict) and name in namespace:
                return namespace[name]
        return None

    def __call__(self, context: CompletionContext) -> SimpleMatcherResult:
        call = _find_open_call(context.full_text[:context.cursor_position])
        if call is None:
            return _no_match()

        obj = self._resolve_object(call.object_name)
        if call.method == 'component' and isinstance(obj, Assembler):
            return self._component_matches(obj, call.args_prefix)
        if call.method in {'run', 'scan'} and isinstance(obj, Simulation):
            return self._simulation_matches(obj, call.method, call.args_prefix)
        return _no_match()

    def _component_matches(self, assembler: Assembler, args_prefix: str) -> dict:
        fragment = _component_type_fragment(args_prefix)
        if fragment is not None:
            return _candidate_result(get_component_names(assembler=assembler), fragment)

        reference_fragment = _relative_reference_fragment(args_prefix)
        if reference_fragment is not None:
            return _candidate_result(get_component_instance_names(assembler), reference_fragment)

        dict_fragment = _keyword_dict_fragment(args_prefix, 'parameters')
        component_name = _component_type_name(args_prefix)
        if dict_fragment is not None and component_name:
            key_fragment = _dict_key_fragment(dict_fragment)
            if key_fragment is not None:
                return _candidate_result(get_component_parameters(component_name, assembler=assembler), key_fragment)

        return _no_match()

    def _simulation_matches(self, simulation: Simulation, method: str, args_prefix: str) -> dict:
        dict_fragment = _keyword_dict_fragment(args_prefix, 'parameters') or _leading_dict_fragment(args_prefix)
        if dict_fragment is not None:
            key_fragment = _dict_key_fragment(dict_fragment)
            if key_fragment is not None:
                return _candidate_result(get_instrument_parameters(simulation), key_fragment)

        segment = _split_top_level(args_prefix)[-1] if args_prefix else ''
        bare_fragment = _bare_identifier_fragment(segment)
        if bare_fragment is not None:
            return _candidate_result(get_runtime_keywords(method), bare_fragment)

        return _no_match()


def register_ipython_matcher(shell=None) -> McCodeIPythonMatcher:
    """Register the mccode-antlr matcher with an IPython shell."""

    get_ipython, _ = _require_ipython()
    shell = shell or get_ipython()
    if shell is None:
        raise RuntimeError('No active IPython shell is available.')

    matcher = McCodeIPythonMatcher(shell=shell)
    custom_matchers = shell.Completer.custom_matchers
    if not any(getattr(existing, 'matcher_identifier', None) == matcher.matcher_identifier for existing in custom_matchers):
        custom_matchers.append(matcher)
    return matcher


def unregister_ipython_matcher(shell=None) -> None:
    """Remove the mccode-antlr matcher from an IPython shell if present."""

    get_ipython, _ = _require_ipython()
    shell = shell or get_ipython()
    if shell is None:
        return

    custom_matchers = shell.Completer.custom_matchers
    custom_matchers[:] = [
        existing
        for existing in custom_matchers
        if getattr(existing, 'matcher_identifier', None) != McCodeIPythonMatcher.matcher_identifier
    ]


def load_ipython_extension(ipython) -> McCodeIPythonMatcher:
    """IPython extension entry point used by ``%load_ext``."""

    return register_ipython_matcher(shell=ipython)


def unload_ipython_extension(ipython) -> None:
    """IPython extension entry point used by ``%unload_ext``."""

    unregister_ipython_matcher(shell=ipython)
