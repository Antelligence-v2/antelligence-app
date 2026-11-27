"""Trust-weighted blind commit-reveal cross-family consensus (Spike C / PR 6).

All tally and trust arithmetic uses fixed-precision ``decimal.Decimal`` (no floats).
Protocol events are recorded onto PR 3's L0 SHA-256 hash chain and replayed
deterministically from genesis to verify bit-identical tallies and trust roots.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any, Mapping, Sequence

from antelligence.record.l0 import Writer, canonical, read_blob, read_events

ZERO = Decimal("0")
ONE = Decimal("1")
QUANT = Decimal("0.00000001")

MIN_TRUST = Decimal("0.05")
MAX_TRUST = Decimal("1.00")
DEFAULT_T0 = Decimal("0.30")
EJECT_THRESHOLD = Decimal("0.10")
EJECT_CONSECUTIVE_ROUNDS = 30
PROBATION_ROUNDS = 20
PROBATION_WEIGHT_CAP = Decimal("1") / Decimal("3")
FAMILY_WEIGHT_CAP = Decimal("0.40")
MIN_FAMILIES = 3
MIN_PARTICIPATING_FAMILIES = 2
MIN_PARTICIPATING_WEIGHT_RATIO = Decimal("0.60")
MIN_N_EFF = Decimal("2.0")
PROMOTE_THRESHOLD = Decimal("0.67")
HIGH_CONF_PASS_P = Decimal("0.80")
SLASH_KAPPA = Decimal("4")
BRIER_BASELINE = Decimal("0.25")
ABSTAIN_DECAY = Decimal("0.98")
MISSING_REVEAL_PENALTY = Decimal("0.90")
PRIOR_SAME_FAMILY = Decimal("0.5")
PRIOR_DIFF_FAMILY = Decimal("0.2")
SHRINKAGE_N0 = Decimal("20")
DEFAULT_WINDOW = 200


class ConsensusError(ValueError):
    """Raised on invalid consensus inputs or replay verification failure."""


class ReplayMismatchError(ConsensusError):
    """Raised when L0 log replay does not reproduce identical tallies or trust roots."""


def _q(val: Decimal) -> Decimal:
    return val.quantize(QUANT, rounding=ROUND_HALF_EVEN)


def _clip(val: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    return max(lo, min(hi, val))


def _exp(val: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 28
        return _q(val.exp())


def _sqrt(val: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 28
        return val.sqrt()


def _to_dec(val: Decimal | int | str) -> Decimal:
    if isinstance(val, float):
        raise TypeError("floats are forbidden in consensus tally/trust arithmetic")
    return Decimal(val)


@dataclass(frozen=True)
class VoterSpec:
    """Static voter registration metadata.

    ``domain`` and ``is_new_family`` are reserved for PR 7 (``DomainTrustBook``
    domain isolation and new-family probation) and are not read by PR 6's
    per-voter ``TrustLedger``.
    """

    voter_id: str
    family: str
    model_id: str = ""
    domain: str = "harness"  # Reserved for PR 7 (DomainTrustBook).
    is_new_family: bool = False  # Reserved for PR 7 (new-family probation).
    dev_brier: Decimal | str | int | None = None


@dataclass
class TrustState:
    trust: Decimal = DEFAULT_T0
    labeled_rounds: int = 0
    probation_left: int = PROBATION_ROUNDS
    low_trust_streak: int = 0
    ejected: bool = False
    recent_abstains: list[int] = field(default_factory=list)
    error_history: list[int | None] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ejected": self.ejected,
            "error_history": list(self.error_history),
            "labeled_rounds": self.labeled_rounds,
            "low_trust_streak": self.low_trust_streak,
            "probation_left": self.probation_left,
            "recent_abstains": list(self.recent_abstains),
            "trust": str(self.trust),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TrustState":
        return cls(
            trust=Decimal(data["trust"]),
            labeled_rounds=int(data["labeled_rounds"]),
            probation_left=int(data["probation_left"]),
            low_trust_streak=int(data["low_trust_streak"]),
            ejected=bool(data["ejected"]),
            recent_abstains=[int(x) for x in data["recent_abstains"]],
            error_history=[None if x is None else int(x) for x in data["error_history"]],
        )


def initial_trust_for(spec: VoterSpec) -> Decimal:
    if spec.dev_brier is None:
        return DEFAULT_T0
    brier = _to_dec(spec.dev_brier)
    raw = Decimal("0.2") + Decimal("1.6") * (BRIER_BASELINE - brier)
    return _q(_clip(raw, Decimal("0.2"), Decimal("0.6")))


class TrustLedger:
    """Deterministic per-voter trust ledger with Hedge-on-Brier updates and slashing.

    PR 6 tracks trust per ``voter_id`` in a single ledger; per-domain isolation
    (``DomainTrustBook``) lands in PR 7.
    """

    def __init__(self, specs: Sequence[VoterSpec] = (), window: int = DEFAULT_WINDOW) -> None:
        self.window = window
        self.specs: dict[str, VoterSpec] = {}
        self.states: dict[str, TrustState] = {}
        for spec in sorted(specs, key=lambda s: s.voter_id):
            self.register(spec)

    def register(self, spec: VoterSpec, trust: Decimal | str | int | None = None, probation_left: int | None = None) -> None:
        self.specs[spec.voter_id] = spec
        t0 = _q(_clip(_to_dec(trust), MIN_TRUST, MAX_TRUST)) if trust is not None else initial_trust_for(spec)
        prob = PROBATION_ROUNDS if probation_left is None else probation_left
        self.states[spec.voter_id] = TrustState(trust=t0, probation_left=prob)

    def snapshot_sha256(self) -> str:
        payload = {vid: self.states[vid].to_dict() for vid in sorted(self.states)}
        return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()

    def clone(self) -> "TrustLedger":
        copy = TrustLedger(window=self.window)
        copy.specs = dict(self.specs)
        copy.states = {vid: TrustState.from_dict(st.to_dict()) for vid, st in self.states.items()}
        return copy

    def update_labeled_round(
        self,
        reveals: Mapping[str, Mapping[str, Any]],
        committed_voters: Sequence[str],
        y: int,
    ) -> None:
        if y not in (0, 1):
            raise ConsensusError("label y must be 0 or 1")
        y_dec = Decimal(y)
        committed_set = set(committed_voters)
        for vid in sorted(self.states):
            st = self.states[vid]
            if st.ejected:
                continue
            rev = reveals.get(vid)
            if rev is None:
                p_dec = Decimal("0.5")
                vote = "ABSTAIN"
                missing_reveal = vid in committed_set
                abstained = True
            else:
                vote = str(rev["vote"])
                if vote == "ABSTAIN":
                    p_dec = Decimal("0.5")
                    missing_reveal = False
                    abstained = True
                else:
                    p_dec = _to_dec(int(rev["p_permille"])) / Decimal(1000)
                    missing_reveal = False
                    abstained = False

            loss = (p_dec - y_dec) * (p_dec - y_dec)
            kappa = SLASH_KAPPA if (vote == "PROMOTE" and p_dec >= HIGH_CONF_PASS_P and y == 0) else ONE
            factor = _exp(-kappa * (loss - BRIER_BASELINE))
            new_t = _clip(st.trust * factor, MIN_TRUST, MAX_TRUST)

            st.recent_abstains.append(1 if abstained else 0)
            if len(st.recent_abstains) > 50:
                st.recent_abstains = st.recent_abstains[-50:]
            if abstained and sum(st.recent_abstains) * 2 > len(st.recent_abstains):
                new_t = _clip(new_t * ABSTAIN_DECAY, MIN_TRUST, MAX_TRUST)
            if missing_reveal:
                new_t = _clip(new_t * MISSING_REVEAL_PENALTY, MIN_TRUST, MAX_TRUST)

            st.trust = _q(new_t)
            st.labeled_rounds += 1
            if st.probation_left > 0:
                st.probation_left -= 1
            if st.trust < EJECT_THRESHOLD:
                st.low_trust_streak += 1
            else:
                st.low_trust_streak = 0
            if st.low_trust_streak >= EJECT_CONSECUTIVE_ROUNDS:
                st.ejected = True

            if abstained:
                err: int | None = None
            else:
                pred = 1 if vote == "PROMOTE" else 0
                err = 1 if pred != y else 0
            st.error_history.append(err)
            if len(st.error_history) > self.window:
                st.error_history = st.error_history[-self.window :]

    def _pair_correlation(self, vid_a: str, vid_b: str) -> Decimal:
        if vid_a == vid_b:
            return ONE
        hist_a = self.states[vid_a].error_history
        hist_b = self.states[vid_b].error_history
        pairs = [(a, b) for a, b in zip(hist_a, hist_b) if a is not None and b is not None]
        n_ij = len(pairs)
        if n_ij == 0:
            return PRIOR_SAME_FAMILY if self.specs[vid_a].family == self.specs[vid_b].family else PRIOR_DIFF_FAMILY
        sum_a = sum(a for a, _ in pairs)
        sum_b = sum(b for _, b in pairs)
        sum_ab = sum(a * b for a, b in pairs)
        n_d = Decimal(n_ij)
        num = n_d * Decimal(sum_ab) - Decimal(sum_a) * Decimal(sum_b)
        den_sq = (n_d * Decimal(sum_a) - Decimal(sum_a * sum_a)) * (n_d * Decimal(sum_b) - Decimal(sum_b * sum_b))
        if den_sq <= ZERO:
            rho_hat = ONE if all(a == b for a, b in pairs) else ZERO
        else:
            rho_hat = num / _sqrt(den_sq)
        shrunk = (n_d / (n_d + SHRINKAGE_N0)) * rho_hat
        return _q(max(ZERO, min(ONE, shrunk)))

    def compute_weights(self, voter_ids: Sequence[str]) -> tuple[dict[str, Decimal], Decimal]:
        """Compute correlation-discounted, probation-capped, family-capped weights and n_eff."""
        vids = sorted(v for v in voter_ids if v in self.states and not self.states[v].ejected)
        if not vids:
            return {}, ZERO

        n = len(vids)
        r_mat: dict[tuple[str, str], Decimal] = {}
        total_r = ZERO
        discounts: dict[str, Decimal] = {}
        for vi in vids:
            row_sum = ZERO
            for vj in vids:
                rho = self._pair_correlation(vi, vj)
                r_mat[(vi, vj)] = rho
                row_sum += rho
            discounts[vi] = ONE / row_sum if row_sum > ZERO else ONE
            total_r += row_sum

        n_eff = _q(Decimal(n * n) / total_r) if total_r > ZERO else ZERO
        weights = {vi: _q(self.states[vi].trust * discounts[vi]) for vi in vids}

        # Cap probationers at 1/3 of total weight.
        prob_ids = [vi for vi in vids if self.states[vi].probation_left > 0]
        if prob_ids and len(prob_ids) < len(vids):
            w_prob = sum(weights[vi] for vi in prob_ids)
            w_non = sum(weights[vi] for vi in vids if vi not in prob_ids)
            if w_non > ZERO and w_prob * Decimal(3) > w_prob + w_non:
                target_prob = w_non / Decimal(2)
                scale = target_prob / w_prob
                for vi in prob_ids:
                    weights[vi] = _q(weights[vi] * scale)

        # Water-filling family cap (<= 0.40 per family).
        families = sorted({self.specs[vi].family for vi in vids})
        if len(families) >= MIN_FAMILIES:
            weights = _water_fill_family_cap(weights, self.specs, FAMILY_WEIGHT_CAP)

        return weights, n_eff


def _water_fill_family_cap(
    weights: dict[str, Decimal],
    specs: Mapping[str, VoterSpec],
    cap_ratio: Decimal,
) -> dict[str, Decimal]:
    out = dict(weights)
    by_fam: dict[str, list[str]] = {}
    for vid in out:
        by_fam.setdefault(specs[vid].family, []).append(vid)

    capped: set[str] = set()
    while True:
        fam_totals = {f: sum(out[v] for v in vs) for f, vs in by_fam.items()}
        uncapped_sum = sum(t for f, t in fam_totals.items() if f not in capped)
        denom = ONE - cap_ratio * Decimal(len(capped))
        if denom <= ZERO or uncapped_sum <= ZERO:
            break
        w_total = uncapped_sum / denom
        newly_capped = [f for f, t in fam_totals.items() if f not in capped and t > cap_ratio * w_total]
        if not newly_capped:
            for f in capped:
                f_cur = fam_totals[f]
                f_target = cap_ratio * w_total
                if f_cur > ZERO:
                    scale = f_target / f_cur
                    for vid in by_fam[f]:
                        out[vid] = _q(out[vid] * scale)
            break
        capped.update(newly_capped)
    return out


def make_commit_hash(
    round_id: str,
    voter_id: str,
    vote: str,
    p_permille: int,
    rationale_sha256: str,
    salt32: str,
) -> str:
    if vote not in ("PROMOTE", "KEEP", "ABSTAIN"):
        raise ConsensusError(f"invalid vote {vote!r}")
    if not (0 <= p_permille <= 1000):
        raise ConsensusError("p_permille must be in [0, 1000]")
    body = canonical(
        {
            "p_permille": p_permille,
            "rationale_sha256": rationale_sha256,
            "round_id": round_id,
            "vote": vote,
            "voter_id": voter_id,
        }
    ).encode("utf-8")
    return hashlib.sha256(body + salt32.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TallyResult:
    round_id: str
    decision: str  # "PROMOTE", "KEEP", "ABSTAIN"
    reason: str
    w_promote: Decimal
    w_keep: Decimal
    w_part: Decimal
    w_all: Decimal
    n_eff: Decimal
    participating_families: int
    roster_families: int
    trust_snapshot_sha256: str

    def to_l0_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "n_eff": str(self.n_eff),
            "participating_families": self.participating_families,
            "reason": self.reason,
            "roster_families": self.roster_families,
            "round_id": self.round_id,
            "trust_snapshot_sha256": self.trust_snapshot_sha256,
            "w_all": str(self.w_all),
            "w_keep": str(self.w_keep),
            "w_part": str(self.w_part),
            "w_promote": str(self.w_promote),
        }


def tally_round(
    round_id: str,
    ledger: TrustLedger,
    roster: Sequence[str],
    valid_reveals: Mapping[str, Mapping[str, Any]],
    *,
    hard_checks_passed: bool = True,
    require_past_probation: bool = False,
) -> TallyResult:
    """Pure deterministic tally over valid reveals using Decimal arithmetic."""
    snap = ledger.snapshot_sha256()
    active_roster = sorted(v for v in roster if v in ledger.states and not ledger.states[v].ejected)
    roster_fams = {ledger.specs[v].family for v in active_roster}

    if not hard_checks_passed:
        return TallyResult(round_id, "ABSTAIN", "hard_checks_failed", ZERO, ZERO, ZERO, ZERO, ZERO, 0, len(roster_fams), snap)
    if len(roster_fams) < MIN_FAMILIES:
        return TallyResult(round_id, "ABSTAIN", "fewer_than_3_families", ZERO, ZERO, ZERO, ZERO, ZERO, 0, len(roster_fams), snap)
    if require_past_probation:
        mature_fams = {ledger.specs[v].family for v in active_roster if ledger.states[v].probation_left == 0}
        if len(mature_fams) < MIN_FAMILIES:
            return TallyResult(round_id, "ABSTAIN", "fewer_than_3_mature_families", ZERO, ZERO, ZERO, ZERO, ZERO, 0, len(roster_fams), snap)

    weights, _ = ledger.compute_weights(active_roster)
    w_all = sum(weights.values(), ZERO)

    part_ids = sorted(v for v in active_roster if v in valid_reveals and valid_reveals[v]["vote"] != "ABSTAIN")
    part_fams = {ledger.specs[v].family for v in part_ids}
    _, n_eff_part = ledger.compute_weights(part_ids)

    w_part = sum((weights[v] for v in part_ids), ZERO)
    w_promote = sum((weights[v] for v in part_ids if valid_reveals[v]["vote"] == "PROMOTE"), ZERO)
    w_keep = sum((weights[v] for v in part_ids if valid_reveals[v]["vote"] == "KEEP"), ZERO)

    if w_all <= ZERO or w_part < MIN_PARTICIPATING_WEIGHT_RATIO * w_all:
        return TallyResult(round_id, "ABSTAIN", "insufficient_participation", w_promote, w_keep, w_part, w_all, n_eff_part, len(part_fams), len(roster_fams), snap)
    if n_eff_part < MIN_N_EFF:
        return TallyResult(round_id, "ABSTAIN", "insufficient_n_eff", w_promote, w_keep, w_part, w_all, n_eff_part, len(part_fams), len(roster_fams), snap)
    if len(part_fams) < MIN_PARTICIPATING_FAMILIES:
        return TallyResult(round_id, "ABSTAIN", "insufficient_participating_families", w_promote, w_keep, w_part, w_all, n_eff_part, len(part_fams), len(roster_fams), snap)

    if w_promote >= PROMOTE_THRESHOLD * w_part:
        decision, reason = "PROMOTE", "supermajority_promote"
    else:
        decision, reason = "ABSTAIN", "below_supermajority"

    return TallyResult(round_id, decision, reason, w_promote, w_keep, w_part, w_all, n_eff_part, len(part_fams), len(roster_fams), snap)


class ConsensusRoundRecorder:
    """Records a blind commit-reveal consensus round onto PR 3's L0 hash chain."""

    def __init__(self, writer: Writer) -> None:
        self.writer = writer

    def _emit(self, kind: str, payload: dict[str, Any], actor: str = "consensus") -> dict[str, Any]:
        return self.writer.append("note", {"text": canonical({"consensus_kind": kind, "payload": payload})}, actor=actor)

    def open_round(
        self,
        round_id: str,
        candidate_diff_sha256: list[str],
        roster: Sequence[str],
        params_sha256: str,
        trust_snapshot_sha256: str,
        evidence_bundle_sha256: str,
    ) -> dict[str, Any]:
        return self._emit(
            "round_open",
            {
                "candidate_diff_sha256": list(candidate_diff_sha256),
                "evidence_bundle_sha256": evidence_bundle_sha256,
                "params_sha256": params_sha256,
                "roster": sorted(roster),
                "round_id": round_id,
                "trust_snapshot_sha256": trust_snapshot_sha256,
            },
        )

    def commit(self, round_id: str, voter_id: str, commit_hash: str) -> dict[str, Any]:
        return self._emit("commit", {"commit_hash": commit_hash, "round_id": round_id, "voter_id": voter_id}, actor=voter_id)

    def close_commits(self, round_id: str, committed_voters: Sequence[str]) -> dict[str, Any]:
        return self._emit("commit_close", {"committed_voters": sorted(committed_voters), "round_id": round_id})

    def reveal(
        self,
        round_id: str,
        voter_id: str,
        vote: str,
        p_permille: int,
        rationale_sha256: str,
        salt32: str,
    ) -> dict[str, Any]:
        return self._emit(
            "reveal",
            {
                "p_permille": p_permille,
                "rationale_sha256": rationale_sha256,
                "round_id": round_id,
                "salt32": salt32,
                "vote": vote,
                "voter_id": voter_id,
            },
            actor=voter_id,
        )

    def record_tally(self, result: TallyResult) -> dict[str, Any]:
        return self._emit("tally", result.to_l0_dict())

    def record_label(self, round_id: str, y: int, new_trust_snapshot_sha256: str) -> dict[str, Any]:
        return self._emit("trust_update", {"new_trust_snapshot_sha256": new_trust_snapshot_sha256, "round_id": round_id, "y": y})


def replay_l0_consensus(
    l0_path: str,
    initial_ledger: TrustLedger,
    *,
    blobs_dir: str | None = None,
    require_past_probation: bool = False,
) -> tuple[TrustLedger, list[TallyResult]]:
    """Replay consensus rounds from an L0 log and verify bit-identical tallies and trust snapshots."""
    events = read_events(l0_path)
    ledger = initial_ledger.clone()
    rounds: dict[str, dict[str, Any]] = {}
    tallies: list[TallyResult] = []

    for ev in events:
        if ev["kind"] != "note":
            continue
        text = ev["data"]["text"]
        if text.startswith("blob:") and blobs_dir is not None:
            text = read_blob(blobs_dir, text.split(":", 1)[1]).decode("utf-8")
        try:
            msg = json.loads(text)
        except ValueError:
            continue
        ckind = msg.get("consensus_kind")
        p = msg.get("payload", {})
        rid = p.get("round_id")
        if ckind == "round_open":
            if p["trust_snapshot_sha256"] != ledger.snapshot_sha256():
                raise ReplayMismatchError(f"round {rid}: initial trust_snapshot_sha256 mismatch")
            rounds[rid] = {"roster": p["roster"], "commits": {}, "closed": False, "reveals": {}}
        elif ckind == "commit":
            r = rounds[rid]
            if not r["closed"] and p["voter_id"] not in r["commits"]:
                r["commits"][p["voter_id"]] = p["commit_hash"]
        elif ckind == "commit_close":
            r = rounds[rid]
            r["closed"] = True
            r["committed_voters"] = list(p["committed_voters"])
        elif ckind == "reveal":
            r = rounds[rid]
            vid = p["voter_id"]
            expected = r["commits"].get(vid)
            if expected is not None:
                actual = make_commit_hash(rid, vid, p["vote"], int(p["p_permille"]), p["rationale_sha256"], p["salt32"])
                if actual == expected:
                    r["reveals"][vid] = p
        elif ckind == "tally":
            r = rounds[rid]
            res = tally_round(rid, ledger, r["roster"], r["reveals"], require_past_probation=require_past_probation)
            if res.to_l0_dict() != p:
                raise ReplayMismatchError(f"round {rid}: tally mismatch: {res.to_l0_dict()} != {p}")
            tallies.append(res)
        elif ckind == "trust_update":
            r = rounds[rid]
            ledger.update_labeled_round(r["reveals"], r.get("committed_voters", list(r["commits"])), int(p["y"]))
            if ledger.snapshot_sha256() != p["new_trust_snapshot_sha256"]:
                raise ReplayMismatchError(f"round {rid}: trust_snapshot_sha256 mismatch after label")

    return ledger, tallies
