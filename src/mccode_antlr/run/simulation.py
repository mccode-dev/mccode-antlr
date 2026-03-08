from __future__ import annotations

from pathlib import Path
from mccode_antlr import Flavor
from mccode_antlr.instr import Instr
from mccode_antlr.compiler.c import CBinaryTarget


class Simulation:
    """A compiled McCode instrument simulation.

    Provides a convenient Python API for compiling an instrument and running single-point
    simulations or parameter scans without using the CLI.

    Usage::

        from mccode_antlr.run import McStas

        sim = McStas(instr).compile('/tmp/build')

        # Single point
        result, dats = sim.run({'x': 1.5, 'y': 2}, ncount=1000)

        # Linear parameter scan
        results = sim.scan({'x': '1:0.5:5', 'y': 2}, ncount=1000)

        # Grid (Cartesian product) scan
        results = sim.scan({'x': '1:1:3', 'y': '10:1:12'}, grid=True, ncount=1000)
    """

    def __init__(self, instr: Instr, flavor: Flavor):
        self.instr = instr
        self.flavor = flavor
        self._binary: Path | None = None
        self._target: CBinaryTarget | None = None
        self._compile_dir: Path | None = None
        self._tmpdir = None  # TemporaryDirectory when compile() owns the dir

    def source(
        self,
        directory: str | Path | None = None,
        *,
        main: bool = True,
        trace: bool = True,
        portable: bool = False,
        runtime: bool = True,
        embed: bool = False,
        verbose: bool = False,
        line_directives: bool = False,
    ):
        from mccode_antlr.translators.c import CTargetVisitor
        directory = directory or Path()
        config = {
            'default_main': main,
            'enable_trace': trace,
            'portable': portable,
            'include_runtime': runtime,
            'embed_instrument_file': embed,
            'verbose': verbose,
            'output': directory / f'{self.instr.name}.c',
        }
        visitor = CTargetVisitor(self.instr, flavor=self.flavor, config=config,
                                 verbose=verbose, line_directives=line_directives)
        visitor.save(filename=config['output'])

    def compile(
        self,
        directory: str | Path | None = None,
        *,
        trace: bool = False,
        source: bool = False,
        verbose: bool = False,
        parallel: bool = False,
        gpu: bool = False,
        process_count: int = 0,
        force: bool = False,
    ) -> 'Simulation':
        """Compile the instrument to a binary.

        :param directory: Directory in which to place the compiled binary and C source.
            When *None* a temporary directory is created automatically and its
            lifetime is tied to this :class:`Simulation` instance — it is cleaned
            up when the instance is garbage collected.
        :param trace: Enable trace mode in the compiled binary.
        :param source: Embed the instrument source in the binary.
        :param verbose: Verbose compiler output.
        :param parallel: Compile with MPI support.
        :param gpu: Compile with OpenACC GPU support.
        :param process_count: MPI process count (0 = system default).
        :param force: Re-compile even if the binary already exists.
        :returns: self, to allow method chaining.
        """
        from os import access, X_OK
        from mccode_antlr.run.runner import mccode_compile

        if directory is None:
            import tempfile
            self._tmpdir = tempfile.TemporaryDirectory(prefix=f'{self.instr.name}_mccode_')
            directory = Path(self._tmpdir.name)
        else:
            self._tmpdir = None
            if not isinstance(directory, Path):
                directory = Path(directory)

        binary_path = directory / self.instr.name
        if binary_path.exists() and access(binary_path, X_OK) and not force:
            self._binary = binary_path
            # Reconstruct a default target so run/scan work without knowing the original settings.
            self._target = CBinaryTarget(mpi=parallel, acc=gpu, count=process_count, nexus=False)
        else:
            target = {'mpi': parallel, 'acc': gpu, 'count': process_count, 'nexus': False}
            config = {'enable_trace': trace, 'embed_instrument_file': source, 'verbose': verbose}
            self._binary, self._target = mccode_compile(
                self.instr, binary_path, self.flavor, target=target, config=config, replace=True
            )

        self._compile_dir = directory
        return self

    def _check_compiled(self):
        if self._binary is None or self._target is None:
            raise RuntimeError(
                "Instrument has not been compiled. Call compile() before run() or scan()."
            )

    def _default_output_dir(self, suffix: str = '') -> Path:
        from datetime import datetime
        base = self._compile_dir if self._compile_dir is not None else Path('.')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return base / f'{self.instr.name}{timestamp}{suffix}'

    @staticmethod
    def _build_runtime_kwargs(
        ncount: int | None,
        seed: int | None,
        trace: bool,
        gravitation: bool | None,
        bufsiz: int | None,
        fmt: str | None,
    ) -> dict:
        return dict(
            ncount=ncount,
            seed=seed,
            trace=trace,
            gravitation=gravitation,
            bufsiz=bufsiz,
            format=fmt,
        )

    def run(
        self,
        parameters: dict | None = None,
        *,
        output_dir: str | Path | None = None,
        ncount: int | None = None,
        seed: int | None = None,
        trace: bool = False,
        gravitation: bool | None = None,
        bufsiz: int | None = None,
        fmt: str | None = None,
        dry_run: bool = False,
        capture: bool = True,
    ) -> tuple:
        """Run a single simulation point.

        :param parameters: Dict mapping instrument parameter names to scalar values
            (int, float, or str).  Range specifications are not accepted here; use
            :meth:`scan` for multi-point runs.  When *None* or an empty dict, all
            instrument parameters use their default values (equivalent to ``mcrun -y``).
        :param output_dir: Directory for output files.  Defaults to a timestamped
            subdirectory inside the compile directory.
        :param ncount: Number of particles to simulate.
        :param seed: RNG seed.
        :param trace: Enable trace mode at runtime.
        :param gravitation: Enable gravitation.
        :param bufsiz: Monitor buffer size.
        :param fmt: Output data format.
        :param dry_run: Print the command without executing it.
        :param capture: Capture subprocess output.
        :returns: ``(result, dats)`` where *result* is the subprocess result and
            *dats* is a dict mapping monitor stem names to loaded data objects.
        :raises ValueError: If any parameter value resolves to more than one point.
        :raises RuntimeError: If :meth:`compile` has not been called first.
        """
        from mccode_antlr.run.runner import mccode_run_compiled, mccode_runtime_parameters, regular_mccode_runtime_dict
        from mccode_antlr.run.range import _make_scanned_parameter, Singular

        self._check_compiled()

        if parameters is None:
            parameters = {}

        # Pass --yes when no explicit parameter values are given so the binary
        # uses its compiled-in defaults rather than entering interactive mode.
        use_defaults = not parameters

        concrete: dict[str, object] = {}
        for k, v in parameters.items():
            if isinstance(v, str) and any(c in v for c in (':', ',')):
                parsed = _make_scanned_parameter(v)
                if len(parsed) != 1:
                    raise ValueError(
                        f"Parameter '{k}={v}' resolves to {len(parsed)} points. "
                        "Use scan() for multi-point runs."
                    )
                concrete[k] = parsed[0]
            else:
                concrete[k] = v

        if output_dir is None:
            output_dir = self._default_output_dir()
        output_dir = Path(output_dir)
        output_dir.parent.mkdir(parents=True, exist_ok=True)

        runtime_kwargs = self._build_runtime_kwargs(ncount, seed, trace, gravitation, bufsiz, fmt)
        args = regular_mccode_runtime_dict(runtime_kwargs)
        pars = mccode_runtime_parameters(args, concrete)
        return mccode_run_compiled(self._binary, self._target, output_dir, pars, capture=capture, dry_run=dry_run, use_defaults=use_defaults)

    def scan(
        self,
        parameters: dict | None = None,
        *,
        output_dir: str | Path | None = None,
        grid: bool = False,
        ncount: int | None = None,
        seed: int | None = None,
        trace: bool = False,
        gravitation: bool | None = None,
        bufsiz: int | None = None,
        fmt: str | None = None,
        dry_run: bool = False,
        capture: bool = True,
    ) -> list:
        """Run a parameter scan.

        :param parameters: Dict mapping instrument parameter names to range specifications.
            Accepted value types:

            * **str** — MATLAB-style range ``'start:step:stop'``, explicit list
              ``'v1,v2,v3'``, or single value ``'1.5'``.
            * **list / tuple** — explicit sequence of values.
            * :class:`~mccode_antlr.run.range.MRange`, :class:`~mccode_antlr.run.range.EList`,
              :class:`~mccode_antlr.run.range.Singular` — pre-constructed range objects.
            * **scalar** (int / float) — held constant across the scan.

            When *None* or an empty dict, the instrument is run once with all default
            parameter values (equivalent to ``mcrun -y``).
        :param output_dir: Root directory for scan output.  Each scan point is written to a
            numbered subdirectory (``0/``, ``1/``, …).  Defaults to a timestamped directory
            inside the compile directory.
        :param grid: When *True*, run the Cartesian product of all parameter ranges; when
            *False* (default) zip the ranges together.
        :param ncount: Number of particles per simulation point.
        :param seed: RNG seed.
        :param trace: Enable trace mode at runtime.
        :param gravitation: Enable gravitation.
        :param bufsiz: Monitor buffer size.
        :param fmt: Output data format.
        :param dry_run: Print commands without executing.
        :param capture: Capture subprocess output.
        :returns: List of ``(result, dats)`` tuples, one per scan point.
        :raises RuntimeError: If :meth:`compile` has not been called first.
        """
        from mccode_antlr.run.runner import mccode_run_scan

        self._check_compiled()

        if parameters is None:
            parameters = {}

        # Pass --yes when no parameters are given so the binary uses its
        # compiled-in defaults rather than entering interactive mode.
        use_defaults = not parameters

        normalized = self._normalize_scan_parameters(parameters)

        if output_dir is None:
            output_dir = self._default_output_dir()
        output_dir = Path(output_dir)

        runtime_kwargs = self._build_runtime_kwargs(ncount, seed, trace, gravitation, bufsiz, fmt)
        return mccode_run_scan(
            self.instr.name,
            self._binary,
            self._target,
            normalized,
            output_dir,
            grid,
            capture=capture,
            dry_run=dry_run,
            use_defaults=use_defaults,
            **runtime_kwargs,
        )

    @staticmethod
    def _normalize_scan_parameters(parameters: dict) -> dict:
        """Convert heterogeneous parameter values to range objects understood by the runner."""
        from mccode_antlr.run.range import MRange, EList, Singular, _make_scanned_parameter, has_len

        normalized: dict = {}
        for k, v in parameters.items():
            if isinstance(v, (MRange, EList, Singular)):
                normalized[k] = v
            elif isinstance(v, str):
                normalized[k] = _make_scanned_parameter(v)
            elif isinstance(v, (list, tuple)):
                normalized[k] = EList(list(v))
            else:
                normalized[k] = Singular(v)

        # Set maximum on unbounded Singular objects so zip terminates.
        max_length = max(
            (len(v) for v in normalized.values() if has_len(v) and not isinstance(v, Singular)),
            default=1,
        )
        for k, v in normalized.items():
            if isinstance(v, Singular) and v.maximum is None:
                normalized[k] = Singular(v.value, max_length)

        return normalized


class McStas(Simulation):
    """A :class:`Simulation` pre-configured for McStas (neutron) instruments."""

    def __init__(self, instr: Instr):
        super().__init__(instr, Flavor.MCSTAS)


class McXtrace(Simulation):
    """A :class:`Simulation` pre-configured for McXtrace (X-ray) instruments."""

    def __init__(self, instr: Instr):
        super().__init__(instr, Flavor.MCXTRACE)
