"""The legacy ant colony (backend/simulation.py) as an engine world."""

from antelligence.worlds.ant_colony.arms import AGENT_TYPES, ARMS, QUEEN_BRAINS, SEEDS, build, needs_llm
from antelligence.worlds.ant_colony.policies import PROMPT_STYLES, ColonyAnt, ColonyPredator, ColonyQueen
from antelligence.worlds.ant_colony.world import QUEEN, AntColonyWorld, Deposits

__all__ = ["AGENT_TYPES", "ARMS", "PROMPT_STYLES", "QUEEN", "QUEEN_BRAINS", "SEEDS", "AntColonyWorld", "ColonyAnt",
           "ColonyPredator", "ColonyQueen", "Deposits", "build", "needs_llm"]
