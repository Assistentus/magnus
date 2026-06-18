"""
fr_lib: Вычислительная гомологическая алгебра для дискретных последовательностей.
Основано на теории fr-кодов (Иванов, Михайлов, Павутницкий, 2020).
"""

from .presentation import TextPresentation
from .magnus import MagnusAlgebra
from .codes import FRCodeRegistry
from .solver import HomologySolver

__version__ = "0.1.0"
__all__ = ["TextPresentation", "MagnusAlgebra", "FRCodeRegistry", "HomologySolver"]
