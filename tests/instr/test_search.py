"""Tests for SEARCH and SEARCH SHELL visitor methods (quote stripping)."""
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock


class TestSearchVisitor(TestCase):
    """The StringLiteral token from the grammar includes surrounding quotes.
    visitSearchPath and visitSearchShell must strip them before use."""

    def _make_ctx(self, literal_text: str):
        """Return a minimal fake context whose StringLiteral() returns *literal_text*."""
        ctx = MagicMock()
        ctx.StringLiteral.return_value = literal_text
        return ctx

    def _make_visitor(self, collected_dirs: list):
        """Return an InstrVisitor-like object whose parent.handle_search_keyword
        appends to *collected_dirs*."""
        from mccode_antlr.instr.visitor import InstrVisitor
        visitor = object.__new__(InstrVisitor)
        parent = MagicMock()
        parent.handle_search_keyword.side_effect = lambda p: collected_dirs.append(p)
        visitor.parent = parent
        return visitor

    def test_search_path_strips_double_quotes(self):
        """visitSearchPath must strip surrounding double-quotes from the token."""
        collected = []
        visitor = self._make_visitor(collected)
        ctx = self._make_ctx('"/some/directory"')
        visitor.visitSearchPath(ctx)
        self.assertEqual(collected, ['/some/directory'])

    def test_search_path_strips_single_quotes(self):
        collected = []
        visitor = self._make_visitor(collected)
        ctx = self._make_ctx("'/another/dir'")
        visitor.visitSearchPath(ctx)
        self.assertEqual(collected, ['/another/dir'])

    def test_search_shell_strips_quotes_from_command(self):
        """visitSearchShell must strip quotes before splitting the command."""
        collected = []
        visitor = self._make_visitor(collected)
        ctx = self._make_ctx('"echo /resolved/compdir"')

        fake_result = MagicMock()
        fake_result.stdout = b'/resolved/compdir\n'

        with patch('subprocess.run', return_value=fake_result) as mock_run:
            visitor.visitSearchShell(ctx)

        # subprocess.run must receive ['echo', '/resolved/compdir'], not
        # ['"echo', '/resolved/compdir"'], and shell=False for safety
        call_args = mock_run.call_args
        self.assertEqual(call_args[0][0], ['echo', '/resolved/compdir'])
        self.assertFalse(call_args[1].get('shell', False), "shell=True is unsafe")
        # Trailing newline in stdout must not produce an empty-string spec
        self.assertEqual(collected, ['/resolved/compdir'])

    def test_search_shell_multi_word_command_unquoted(self):
        """A realistic multi-word command like 'cmd --flag value' must split correctly."""
        collected = []
        visitor = self._make_visitor(collected)
        ctx = self._make_ctx('"readout-config --show compdir"')

        fake_result = MagicMock()
        fake_result.stdout = b'/opt/readout/components\n'

        with patch('subprocess.run', return_value=fake_result) as mock_run:
            visitor.visitSearchShell(ctx)

        args = mock_run.call_args[0][0]
        # First arg must not start with a quote character
        self.assertFalse(args[0].startswith('"'),
                         f"First arg still has a leading quote: {args!r}")
        self.assertEqual(args, ['readout-config', '--show', 'compdir'])
        self.assertFalse(mock_run.call_args[1].get('shell', False),
                         "shell=True is unsafe for user-supplied commands")
