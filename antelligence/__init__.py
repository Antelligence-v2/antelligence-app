"""Antelligence engine: a verifiable stigmergic substrate for agent swarms.

The ``kernel`` package owns coordination (signals, fields), trust (memory,
admission, verification) and execution (scheduler, event log). Worlds plug in
by implementing :class:`antelligence.kernel.types.World`; the kernel never
imports a world.
"""

__version__ = "0.1.0"
