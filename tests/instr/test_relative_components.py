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


def timed_hash(obj):
    from time import time_ns
    start = time_ns()
    value = hash(obj)
    return (time_ns() - start) / 1e9, value


def test_chained_hashes_are_independent():
    from math import sqrt
    instr = make_instr()
    hashes = set()
    times = []
    for index, instance in enumerate(instr.components):
        time, hash_val = timed_hash(instance)
        assert hash_val not in hashes
        hashes.add(hash_val)
        times.append(time)
        average_time = sum(times) / len(times)
        stddev_time = sqrt(sum((t - average_time)**2 for t in times)) / len(times)
        print(f'{instance.name}: {time} ({hash_val})')
        assert abs(average_time - time) <= 10 * stddev_time


