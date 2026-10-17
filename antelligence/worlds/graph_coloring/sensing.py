"""Sensing layer for the coloring world: one agent's LocalView -> a short state in words.

Colour NAMES in the text, typed action ids (``colour_3``) in the action list. Counting and set logic
(who shares my colour, which colours are taken or free) is done here, in code, never left to the model.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from antelligence.kernel.decision import Question, SensedState
from antelligence.kernel.types import NOOP, LocalView
from antelligence.worlds.graph_coloring.world import COLOUR_NAMES, colour_action


def _name(index: Any) -> str:
    return COLOUR_NAMES[index] if isinstance(index, int) else "nothing"


class ColoringSensor:
    def describe(self) -> Dict[str, Any]:
        return {"sensor": "graph_coloring", "version": 1}

    def sense(self, view: LocalView) -> SensedState:
        obs: Mapping[str, Any] = view.observation
        rnd, rounds, palette, mine = obs["round"], obs["rounds"], obs["palette"], obs["colour"]
        heard: Mapping[str, Mapping[str, Any]] = obs["heard"]
        parts: List[str] = []
        same: List[str] = []
        silent: List[str] = []
        flipped: List[str] = []
        for u in obs["neighbours"]:
            h = heard[u]
            known = h["colour"] is not None
            notes: List[str] = []
            if known and mine is not None and h["colour"] == mine:
                same.append(u)
            if h["fresh"]:
                phrase = f"agent {u} said {_name(h['colour'])}"
                if h["prev"] is not None and h["prev"] != h["colour"]:
                    notes.append(f"was {_name(h['prev'])}")
                    flipped.append(u)
            elif rnd == 1:
                phrase = f"agent {u}"
            else:
                silent.append(u)
                phrase = f"agent {u} sent nothing this round"
                if known:
                    notes.append(f"last said {_name(h['colour'])}")
            if u in same:
                notes.append("same as yours")
            if notes:
                phrase += f" ({', '.join(notes)})"
            parts.append(phrase)
        taken = sorted({h["colour"] for h in heard.values() if h["colour"] is not None})
        free = [c for c in range(palette) if c not in taken]
        text = f"Your colour: {_name(mine) if mine is not None else 'none yet'}. Neighbours: {', '.join(parts)}."
        if rnd == 1:
            text += " Nothing heard yet."
        elif taken:
            text += f" Colours your neighbours use: {', '.join(_name(c) for c in taken)}."
        text += f" Colours available: {', '.join(COLOUR_NAMES[:palette])}. Round {rnd} of {rounds}."
        actions = {colour_action(i): f"Take {COLOUR_NAMES[i]}" for i in range(palette)}
        actions[NOOP] = "Keep your current colour"
        checks: Dict[str, Question] = {}
        if rnd >= 2 and obs["neighbours"]:
            checks["heard_all"] = Question("noul", "Did every neighbour send you a message this round?",
                                           criteria={"true": "all neighbours sent a message",
                                                     "false": "at least one neighbour sent nothing"})
        if flipped:
            checks["reports_true"] = Question(
                "noul", "Are all your neighbours' reports honest, with changes only where a clash forced them?",
                criteria={"true": "no neighbour's report looks false",
                          "false": "a neighbour keeps changing colour for no reason"})
        fields = {"agent": obs["agent"], "round": rnd, "rounds": rounds, "palette": palette, "colour": mine,
                  "neighbours": list(obs["neighbours"]), "heard": {u: dict(h) for u, h in heard.items()},
                  "same": same, "silent": silent, "flipped": flipped, "taken": taken, "free": free}
        return SensedState(text=text, fields=fields, actions=actions, checks=checks)
