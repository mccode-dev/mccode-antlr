# Contributing to mccode-antlr

Thank you for helping. mccode-antlr is maintained alongside other work, mostly by one
person, so replies to issues and reviews of pull requests can take a while. This page
says what makes a contribution quick to review and merge.

## What belongs here

mccode-antlr is an alternative translator for the McStas and McXtrace languages. The
classic flex/bison `mcstas` and `mcxtrace` set the standard: for the same input it
should produce equivalent C, and differences from them are bugs unless they were made
on purpose and documented.

- **Grammar, translation, the Python API and tooling** (the `Assembler`, registries,
  caches, running and reading output) belong here.
- **Component (`.comp`) files and the C runtime** belong upstream in
  [McCode](https://github.com/mccode-dev/McCode). mccode-antlr downloads them from
  there, by McCode version.

## Reporting a bug

Please include:

- the smallest `.instr` (and any `.comp`) that shows the problem;
- what you expected and what happened, with the full error message;
- your mccode-antlr version (`python -c "import mccode_antlr; print(mccode_antlr.__version__)"`),
  the McCode version it uses (`mccode-antlr config get mccode_pooch.tag`), your platform
  and Python version, and which optional extras are installed;
- for "behaves differently from McStas", what the classic `mcstas` does with the same file.

## Proposing a change

Small, self-contained fixes can go straight to a pull request. For anything larger (a
new feature, a change to the grammar, or one to the public API), please open an issue
first, so we can agree on the approach before you spend time on it.

## Setting up and running the tests

```bash
git clone https://github.com/mccode-dev/mccode-antlr.git
cd mccode-antlr
pip install -e ".[test,hdf5,mcpl]"
python -m pytest
```

Some things to know about the test suite:

- **It downloads McCode.** Components and runtime files come from McCode on GitHub and
  are cached on first use (`mccode-antlr cache list` shows what is cached), so the first
  run needs a network connection.
- **CI pins the McCode version.** Tests run against McCode `v3.8.7` on CI, while a local
  run uses the newest version by default. If your change touches compiling or running
  instruments, run the suite both ways:

  ```bash
  MCCODEANTLR_MCCODE_POOCH__TAG=v3.8.7 python -m pytest
  python -m pytest
  ```

- **Some tests skip rather than fail.** Tests that compile instruments need a working C
  compiler; MCPL tests need `mcpl-config`; others need an optional package (scipp,
  IPython). Check the skips in pytest's summary (`python -m pytest -rs`): a skipped test
  has not passed.
- **Optional dependencies are optional.** The `test` extra installs scipp, so a normal
  run never tests what happens without it. If you change code that uses an optional
  package, also run the suite in a fresh environment with a plain `pip install .` (CI
  has a job that does exactly that).

## Pull requests

What helps a pull request get merged:

- **One change per pull request.** Related fixes can share one; unrelated ones should
  not. If several pull requests depend on each other, say so and in what order.
- **A test that fails without your change** and passes with it.
- **A description that says what you verified**: which tests you ran, and against
  which McCode version, not only what the change does.
- **Commit messages that explain why** the change is needed, not just what it does.
- **No unrelated changes**: no reformatting or renaming outside what the change needs.
  Match the style of the code around it.
- **Documentation updated** (README, `docs/`, docstrings) when behaviour changes.

Release notes are generated from pull request labels, so we will add one when merging:
`breaking-change` for anything that changes existing behaviour or API, `enhancement` for
new features, `ignore-for-release` for changes users will not notice. Suggestions are
welcome.

## AI-assisted contributions

Contributions written with AI assistants are welcome, on the same terms as any other.
The person opening the issue or pull request is its author: you should have read the
change, run the tests, and be able to answer questions about it. A `Co-Authored-By`
trailer is fine but not required. Please keep the number of open issues and pull
requests in proportion to the change: several small related fixes are easier to review
together, or as a short series that says how they depend on each other.

## License

By contributing, you agree that your contribution is licensed under the project's
[BSD 3-Clause License](LICENSE).
