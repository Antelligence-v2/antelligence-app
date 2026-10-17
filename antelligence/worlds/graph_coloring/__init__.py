"""Graph coloring: a seeded port of AgentsNet's coloring task (MIT; https://github.com/floriangroetschla/AgentsNet)."""

from antelligence.worlds.graph_coloring.pilot import GRAPH_COLORING, GraphColoringPilot
from antelligence.worlds.graph_coloring.sensing import ColoringSensor
from antelligence.worlds.graph_coloring.world import GraphColoringWorld, colour_action, parse_colour_action

__all__ = ["GRAPH_COLORING", "ColoringSensor", "GraphColoringPilot", "GraphColoringWorld", "colour_action",
           "parse_colour_action"]
