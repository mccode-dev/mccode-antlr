"""Monte Carlo Particle Ray Tracing compiler, Volume 4"""
import mccode_antlr.grammar
__author__ = "Gregory Tucker"
__affiliation__ = "European Spallation Source ERIC"

from .version import version
__version__ = version()

from enum import IntEnum

class Flavor(IntEnum):
    """The specializations of the McCode language.

    Enumerated _values_ follow the McCode _project_ number.
    """
    BASE=0
    MCSTAS=1
    MCXTRACE=2

    def __str__(self):
        options = {
            Flavor.BASE: 'base',
            Flavor.MCSTAS: 'McStas',
            Flavor.MCXTRACE: 'McXTrace'
        }
        return options[self]

    def url(self) -> str:
        options = {
            Flavor.MCSTAS: 'https://www.mcstas.org',
            Flavor.MCXTRACE: 'https://www.mcxtrace.org'
        }
        return options[self]


__all__ = ["__author__", "__affiliation__", "__version__", "version", "Flavor"]
