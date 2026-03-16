"""
Instruments are allowed to define components relative to any preceding component

Some instrument take this to an extreme and introduce ever-expanding component
depends on chains. One such example instrument is ILL_H142, which should be convertible
to C code in a finite length of time.
A non-optimal `hash` implementation can cause every component to need to calculate
the hash of its predecessor, resulting in O(2^(N+1)) runtime to calculate the hash
for all components.

This simplified variant of ILL_H142 is only intended to verify that the scaling problem
is fixed.
"""
from textwrap import dedent

ILL_H142_EXTRACT = dedent(
    """
    DEFINE INSTRUMENT ILL_H142(m=1, lambda=10, dlambda=9.9, gH=0.12, mip=1)
    DECLARE
    %{
      /* VCS (H1) source parameters */
      double sT1=216.8,sI1=1.24e+13;
      double sT2=33.9, sI2=1.02e+13;
      double sT3=16.7 ,sI3=3.0423e+12;
      /* guide coating parameters */
      double gR0          = 1;
      double gQc          = 0.021;
      double gAlpha       = 4.07;
      double gW           = 1.0/300.0;
      /* gaps and Al windows parameters */
      double Al_Thickness = 0.002;
      double gGap         = 0.001;
      /* guide curvatures */
      double gRh          = 2700; /* anti-clockwise */
      /* guide section parameters (total length/number of elements) */
      double L_H142_2 =6.0  /6,  Rh_H142_2 =0;
    
      /* capture flux positions from moderator: 21.4    28.4    61.2 */
    
    %}
    INITIALIZE
    %{
      /* Element rotations = Element length / Curvature Radius * RAD2DEG */
      if (gRh) {
        Rh_H142_2  = L_H142_2 /gRh*RAD2DEG;
      }
    %}
    
    TRACE
    COMPONENT Origin = Progress_bar()
      AT (0,0,0) ABSOLUTE
    
    COMPONENT VCS = Source_gen(
      yheight  = 0.22,
      xwidth   = 0.14,
      dist     = 2.525,
      focus_xw = 0.038,
      focus_yh = 0.2,
      lambda0  = lambda,
      dlambda  = dlambda,
      T1       = sT1,
      I1       = sI1,
      T2       = sT2,
      I2       = sI2,
      T3       = sT3,
      I3       = sI3,
      verbose  = 1)
      AT (0, 0, 0) RELATIVE Origin
    
    COMPONENT Al_window1 = Al_window(thickness=Al_Thickness)
    AT (0,0,0.21) RELATIVE VCS
    
    COMPONENT Al_window2 = Al_window(thickness=Al_Thickness)
    AT (0,0,0.61) RELATIVE VCS
    
    COMPONENT Al_window3 = Al_window(thickness=Al_Thickness)
    AT (0,0,0.78) RELATIVE VCS
    
    COMPONENT Al_window4 = Al_window(thickness=Al_Thickness)
    AT (0,0,0.92) RELATIVE VCS
    
    COMPONENT Al_window5 = Al_window(thickness=Al_Thickness)
    AT (0,0,2.43) RELATIVE VCS
    
    /* H142-1: L=3.17 m in 1 element. no curvature */
    
    COMPONENT PinkCarter = Guide_gravity(
      w1=0.038, h1=0.2, w2=0.032, h2=0.2, l=3.170,
      R0=gR0, Qc=gQc, alpha=gAlpha, m=mip, W=gW)
    AT (0,0,2.525) RELATIVE VCS
    
    COMPONENT FirstObturator = Guide_gravity(
      w1=0.031, h1=0.2, w2=0.031, h2=0.2, l=0.228,
      R0=gR0, Qc=gQc, alpha=gAlpha, m=mip, W=gW)
    AT (0,0,3.17+0.02) RELATIVE PinkCarter
    
    /* ******************** swiming pool guide ******************** */
    
    /* H142-2: L=5.5 m in 6 elements R horiz=2700 m */
    
    COMPONENT H142_2 = Arm()
    AT (0,0,3.59) RELATIVE PinkCarter
    
    COMPONENT H142_2_In = Al_window(thickness=Al_Thickness)
    AT (0,0,0) RELATIVE PREVIOUS
    
    COMPONENT H142_2_1 = Guide_gravity(
      w1=0.03, h1=0.2, w2=0.03, h2=0.2, l=L_H142_2,
      R0=gR0, Qc=gQc, alpha=gAlpha, m=m, W=gW)
    AT (0,0,Al_Thickness+gGap) RELATIVE PREVIOUS ROTATED (0,Rh_H142_2,0) RELATIVE PREVIOUS
    
    COMPONENT H142_2_2 = COPY(PREVIOUS)
    AT (0,0,L_H142_2+gGap) RELATIVE PREVIOUS ROTATED (0,Rh_H142_2,0) RELATIVE PREVIOUS
    
    COMPONENT H142_2_3 = COPY(PREVIOUS)
    AT (0,0,L_H142_2+gGap) RELATIVE PREVIOUS ROTATED (0,Rh_H142_2,0) RELATIVE PREVIOUS
    
    COMPONENT H142_2_4 = COPY(PREVIOUS)
    AT (0,0,L_H142_2+gGap) RELATIVE PREVIOUS ROTATED (0,Rh_H142_2,0) RELATIVE PREVIOUS
    
    COMPONENT H142_2_5 = COPY(PREVIOUS)
    AT (0,0,L_H142_2+gGap) RELATIVE PREVIOUS ROTATED (0,Rh_H142_2,0) RELATIVE PREVIOUS
    
    COMPONENT H142_2_6 = COPY(PREVIOUS)
    AT (0,0,L_H142_2+gGap) RELATIVE PREVIOUS ROTATED (0,Rh_H142_2,0) RELATIVE PREVIOUS
    
    COMPONENT H142_2_Out = Al_window(thickness=Al_Thickness)
    AT (0,0,L_H142_2+gGap) RELATIVE PREVIOUS
    
    /* The END token marks the instrument definition end */
    END
    """
)

def make_instr():
    from mccode_antlr.loader import parse_mcstas_instr
    instr = parse_mcstas_instr(ILL_H142_EXTRACT)
    return instr


def test_instr_parses():
    from mccode_antlr.instr import Instr
    instr = make_instr()
    assert isinstance(instr, Instr)


def test_chained_hashes_are_independent():
    """
    Verify that hashing all components in a chained-relative instrument runs in
    O(N) time, not O(2^N).

    The old per-component statistical bound (using standard error σ/√N) was
    overly sensitive: it tightened with N, so OS scheduling jitter on a single
    component could fail the test on CI.

    Instead we use a coarse total-time bound.  With the fix applied, hashing all
    N components 3 times should complete well under 5 seconds on any machine.
    If the O(2^N) regression is reintroduced, the same work takes ~300 seconds,
    which will clearly exceed the threshold.
    """
    from time import time_ns

    instr = make_instr()
    hashes = set()

    repetitions = 3
    total_time_limit = 5.0
    start = time_ns()

    def elapsed(msg: str | None = None) -> float:
        seconds = (time_ns() - start) / 1e9
        if msg is None:
            msg = "Cumulative hashing"
        assert seconds < total_time_limit, (
            f"{msg} took {elapsed():.2f}s (limit {total_time_limit}s) — "
            f"possible O(2^N) regression in Instance.__hash__"
        )
        return seconds

    # Uniqueness check (fast if no regression in hash)
    for instance in instr.components:
        h = hash(instance)
        assert h not in hashes, f"hash collision on {instance.name}"
        elapsed()
        hashes.add(h)

    # Total-time bound over multiple repetitions
    for _ in range(repetitions):
        for instance in instr.components:
            hash(instance)
            elapsed()

    print(f"Hashed {len(instr.components)} components × {repetitions} reps in {elapsed():.3f}s")



