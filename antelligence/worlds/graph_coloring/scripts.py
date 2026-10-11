"""Hand-written scripts for the coloring world: S, and S' for v1 and v2. No model calls.

All scripts read the same :class:`SensedState` (via the world's sensor) that every model arm sees.

S -- patient name-priority greedy. Lower ids have priority: an agent colours itself exactly once, with the
  lowest colour none of its neighbours has announced, but only after it has heard a settled colour from EVERY
  lower-id neighbour ("settled" = the neighbour's latest report is not a change from its previous one). It
  never guesses: an agent still missing information when the rounds run out stays uncoloured. Agents with no
  lower neighbour colour themselves in round 1. Why this S: it is exact whenever the information arrives,
  and 'wait for your higher-priority neighbours' is how a careful agent reads AgentsNet's coloring task.
  On a base graph the chain of waiting can be longer than the 4 rounds, so S is not perfect there.

S' (v1, lost messages) -- resend until acknowledged, within the world's rules. Messages carry the sender's
  colour plus an acknowledgement (the colour it last heard from the receiver); taking a colour announces it.
  S' re-takes its own colour every round until every neighbour has acknowledged it, so a lost announcement is
  repeated. It also knows silence can mean loss rather than 'not coloured yet', so in the last round it colours
  itself from whatever it has heard instead of waiting.

S' (v2, one liar) -- told the liar's id: ignores everything that agent says (never waits for it, never flags
  its changing reports as unsettled, never avoids its colour).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from antelligence.kernel.decision import Sensor
from antelligence.kernel.types import NOOP, Intent, LocalView
from antelligence.worlds.graph_coloring.world import colour_action


class PatientGreedy:
    """S. The base class for S' too: subclasses switch on one adaptation each."""

    name = "S:patient_greedy"
    resend_until_acked = False
    guess_in_last_round = False

    def __init__(self, sensor: Sensor, *, ignore: Optional[str] = None) -> None:
        self._sensor = sensor
        self.ignore = ignore

    def describe(self) -> Dict[str, Any]:
        return {"policy": self.name, "ignore": self.ignore}

    def decide(self, view: LocalView) -> Intent:
        choice = self.choose(self._sensor.sense(view).fields)
        return Intent(NOOP) if choice is None else Intent(colour_action(choice))

    def choose(self, f: Dict[str, Any]) -> Optional[int]:
        me, heard = f["agent"], f["heard"]
        nbrs = [u for u in f["neighbours"] if u != self.ignore]
        if f["colour"] is not None:
            # Resend: keep announcing my colour until every neighbour has acknowledged it.
            if self.resend_until_acked and any(heard[u]["ack"] != f["colour"] for u in nbrs):
                return f["colour"]
            return None
        lower = [u for u in nbrs if int(u) < int(me)]
        settled = all(heard[u]["colour"] is not None and u not in f["flipped"] for u in lower)
        if settled or (self.guess_in_last_round and f["round"] >= f["rounds"]):
            taken = {heard[u]["colour"] for u in nbrs if heard[u]["colour"] is not None}
            return next((c for c in range(f["palette"]) if c not in taken), 0)
        return None


class ResendUntilAcked(PatientGreedy):
    name = "S':resend_until_acked"
    resend_until_acked = True
    guess_in_last_round = True


class IgnoreLiar(PatientGreedy):
    name = "S':ignore_liar"

    def __init__(self, sensor: Sensor, liar: str) -> None:
        super().__init__(sensor, ignore=liar)
