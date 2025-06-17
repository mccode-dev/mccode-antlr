"""Monte Carlo Particle Ray Tracing compiler, Volume 4"""
import mccode_antlr.grammar
__author__ = "Gregory Tucker"
__affiliation__ = "European Spallation Source ERIC"

from .version import version
__version__ = version()

from enum import Enum

class Flavor(Enum):
    MCSTAS=1
    MCXTRACE=2

    def __str__(self):
        return 'McStas' if self==Flavor.MCSTAS else 'McXtrace'


__all__ = ["__author__", "__affiliation__", "__version__", "version", "Flavor"]
