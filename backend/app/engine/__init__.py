"""The machine (Doc 04 §04). Alpha loop, Boundary, Stray detection — scaffolded interfaces.

These are the seams the engine work (Jun 13-15) fills in. Kept as small, typed
placeholders so the API and bus can be wired against them today.
"""

from .boundary import Boundary
from .stray import StrayDetector

__all__ = ["Boundary", "StrayDetector"]
