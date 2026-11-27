"""Small summaries of a reply's token log-probabilities, so a run can keep how sure a model was without storing every
token.

Two uses, both borrowed from proven work:

* **How sure a model is of its answer letter** (the confidence gate; AutoMix, Madaan et al. 2023, and the
  answer-probability cascades of FrugalGPT): at the token where the model wrote its option letter, the chance it gave
  that letter against the other option letters.
* **How sure it was along the way** (DeepConf, Fu et al. 2025, "Deep Think with Confidence"): a token's confidence is
  ``-(1/k) * sum of the top-k log-probabilities`` there (high when one choice dominates), averaged over the whole
  reply, over its last tokens ("tail"), and its lowest average over a sliding window ("lowest group").

Two server shapes are read:

* OpenAI's (also ``mlx_lm.server`` 0.2x and later): ``{"content": [{"token", "logprob", "top_logprobs": [{"token",
  "logprob"}, ...]}, ...]}``. ``mlx_lm.server`` puts the top alternatives in an arbitrary order and copies the first
  one into the entry, so this code never assumes the entry is the token that was sampled: it reads the alternatives.
* Older ``mlx_lm.server``: ``{"token_logprobs": [...], "tokens": [ids], "top_logprobs": [{id: logprob}, ...]}``.
  It has no token text, so only the "along the way" numbers can be read, never the answer letter's chance.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

TAIL = 32            # tokens in the "tail" confidence and the sliding window
SLOT_SCAN = 12       # the answer letter is looked for in the last this-many tokens first
_SPACE = {"Ġ": " ", "▁": " ", "Ċ": "\n", "ĉ": "\t"}


def norm_token(tok: str) -> str:
    """A tokenizer piece as plain text, stripped of spaces, quotes and brackets: ``'Ġ"C'`` -> ``'C'``."""
    for k, v in _SPACE.items():
        tok = tok.replace(k, v)
    return tok.strip().strip("\"'`()[]{}.,:;*").strip()


def _alts(entry: Mapping[str, Any]) -> List[Tuple[Optional[str], float]]:
    """(text or None, logprob) for each alternative at one position (the entry itself when no list is given)."""
    alts = entry.get("top_logprobs")
    out: List[Tuple[Optional[str], float]] = []
    if isinstance(alts, list) and alts:
        for a in alts:
            if isinstance(a, Mapping) and isinstance(a.get("logprob"), (int, float)):
                tok = a.get("token")
                out.append((tok if isinstance(tok, str) else None, float(a["logprob"])))
    elif isinstance(entry.get("logprob"), (int, float)):
        tok = entry.get("token")
        out.append((tok if isinstance(tok, str) else None, float(entry["logprob"])))
    return out


def _positions(raw: Any) -> List[List[Tuple[Optional[str], float]]]:
    if not isinstance(raw, Mapping):
        return []
    content = raw.get("content")
    if isinstance(content, list):
        return [a for a in (_alts(e) for e in content if isinstance(e, Mapping)) if a]
    tops = raw.get("top_logprobs")
    if isinstance(tops, list) and tops:                      # older mlx_lm: {id: logprob} per position, no text
        out = []
        for d in tops:
            if isinstance(d, Mapping):
                vals = [(None, float(v)) for v in d.values() if isinstance(v, (int, float))]
                if vals:
                    out.append(vals)
        return out
    lps = raw.get("token_logprobs")
    if isinstance(lps, list):
        return [[(None, float(v))] for v in lps if isinstance(v, (int, float))]
    return []


def _conf(alts: Sequence[Tuple[Optional[str], float]]) -> float:
    return -sum(lp for _, lp in alts) / len(alts)


def letter_slot(positions: Sequence[Sequence[Tuple[Optional[str], float]]], letters: Sequence[str] = "ABCDE"
                ) -> Optional[Dict[str, float]]:
    """The chances of each option letter at the token where the reply wrote its answer letter, or None.

    The answer comes last in the asked form (``{"reason": ..., "answer": "C"}``), so the slot is the last of the final
    ``SLOT_SCAN`` tokens whose alternatives include an option letter. When none does, the last token anywhere whose
    alternatives hold two or more different letters (a real choice between options)."""
    letters = tuple(letters)

    def found(alts) -> Dict[str, float]:
        got: Dict[str, float] = {}
        for tok, lp in alts:
            t = norm_token(tok) if tok is not None else ""
            if t in letters:
                got[t] = got.get(t, 0.0) + math.exp(lp)
        return got

    n = len(positions)
    for i in range(n - 1, max(-1, n - 1 - SLOT_SCAN), -1):
        got = found(positions[i])
        if got:
            return got
    for i in range(n - 1, -1, -1):
        got = found(positions[i])
        if len(got) >= 2:
            return got
    return None


def summarize(raw: Any, letters: Sequence[str] = "ABCDE") -> Optional[Dict[str, Any]]:
    """A few numbers from a ``logprobs`` block (None when it holds none). Small enough to keep with every call."""
    pos = _positions(raw)
    if not pos:
        return None
    confs = [_conf(a) for a in pos]
    w = min(TAIL, len(confs))
    groups = [sum(confs[i:i + w]) / w for i in range(0, len(confs) - w + 1)]
    slot = letter_slot(pos, letters)
    return {"n": len(pos), "k": max(len(a) for a in pos), "conf": round(sum(confs) / len(confs), 4),
            "tail_conf": round(sum(confs[-w:]) / w, 4), "low_group": round(min(groups), 4),
            "text": any(t is not None for a in pos for t, _ in a),
            "slot": {k: round(v, 6) for k, v in slot.items()} if slot else None}


def letter_sure(summary: Optional[Mapping[str, Any]], answer: Optional[str]) -> Optional[float]:
    """How sure the model was of ``answer``: its chance at the answer slot, out of all option letters there.

    None when it can't be told (no summary, no token text, no slot, or no answer). 0.0 when the slot was found but the
    answer was not among its top letters (it was sampled from the long tail)."""
    if not summary or not answer or not summary.get("slot"):
        return None
    slot = summary["slot"]
    total = sum(slot.values())
    if total <= 0:
        return None
    return round(slot.get(answer, 0.0) / total, 6)


def cached_tokens(usage: Any) -> Optional[int]:
    """``usage.prompt_tokens_details.cached_tokens`` (OpenAI's field, also sent by ``mlx_lm.server`` 0.2x+), or None."""
    if not isinstance(usage, Mapping):
        return None
    det = usage.get("prompt_tokens_details")
    if isinstance(det, Mapping) and type(det.get("cached_tokens")) is int and det["cached_tokens"] >= 0:
        return int(det["cached_tokens"])
    return None
