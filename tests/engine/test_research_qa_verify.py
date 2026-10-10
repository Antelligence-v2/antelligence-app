"""Verified claim admission, lenient parsing and plurality control for the research_qa world."""

import copy

import pytest

from backend.research_data import load_bundle

from antelligence.kernel import events as ev
from antelligence.kernel.aggregate import FAILED, UNVERIFIED, VERIFIED, Aggregator, Vote
from antelligence.worlds.research_qa import ResearchQAWorld, ScriptedQAPolicy, build
from antelligence.worlds.research_qa.policies import QAPolicy, VERIFIED_CLAIMS_SYSTEM, verified_claims_system
from antelligence.worlds.research_qa.verify import verify_claim
from antelligence.providers import FakeProvider

BUNDLE = {t["task_id"]: t for t in load_bundle()["tasks"]}
MED = BUNDLE["pubmedqa:22186742"]
FIN = BUNDLE["finqa:UPS/2006/page_32.pdf-1"]  # $148.92 - $100.00 = 48.92 (table_1)

# Pinned on the unmodified world (before verified admission existed): seed=3, ScriptedQAPolicy.
PINS = {
    (MED["task_id"], "independent_vote"): (
        "684d46fc3c74459601759bae1e6e61afe130947d51c81a2c81042072b81a522c",
        "d75e5c0215f122fb974899884f1311736ea19482d4feb08e85e9e2f95669ab9d",
        {"answer": "yes", "correct": False, "domain": "medical", "final_answers": ["yes", "no", "yes"], "invalid": 0,
         "protocol": "independent_vote", "rounds_completed": 1, "status": "completed", "task_id": MED["task_id"]}),
    (MED["task_id"], "evidence_exchange"): (
        "fd34a9dbc895d12ecec1801ec7c6f152dc6d40fba5c6069d913240d450ef6608",
        "dc51f5b02e52f9b04fe0bff144c8b1fdafa9e639b5f224d319de862bc69d7ba7",
        {"answer": "yes", "correct": False, "domain": "medical", "final_answers": ["yes", "no", "yes"], "invalid": 0,
         "protocol": "evidence_exchange", "rounds_completed": 2, "status": "completed", "task_id": MED["task_id"]}),
    (FIN["task_id"], "independent_vote"): (
        "d485ac733e0b277776c221109d4a9afd095504b93b5055cec50f68be2c385919",
        "7a87196376a7b9dba2581ce920a02535c618389bd00a702cbd8edf2e7b192fe5",
        {"answer": "48.92", "correct": True, "domain": "finance", "final_answers": ["48.92", "48.92", "10"],
         "invalid": 0, "protocol": "independent_vote", "rounds_completed": 1, "status": "completed",
         "task_id": FIN["task_id"]}),
    (FIN["task_id"], "evidence_exchange"): (
        "8a7f55467caecba553099db369db8622dbb238d75890ba28c51fd99bb57e42af",
        "5e2831edb2b8ea8235578ab706c8b15e5b03e2872b224fd95b1e2a0dc4f17c4e",
        {"answer": "48.92", "correct": True, "domain": "finance", "final_answers": ["48.92", "48.92", "10"],
         "invalid": 0, "protocol": "evidence_exchange", "rounds_completed": 2, "status": "completed",
         "task_id": FIN["task_id"]}),
}


def legacy_factory(task):
    def make(agent):
        i = int(agent.rsplit("-", 1)[1])

        def reply(view):
            ids = [e["id"] for e in view.observation["task"]["evidence"]]
            ans = ["yes", "no", "yes"][i - 1] if task["answer_type"] == "choice" else ["48.92", "48.92", "10"][i - 1]
            return {"answer": ans, "evidence_ids": ids[:1], "brief": "b"}

        return ScriptedQAPolicy(reply)

    return make


@pytest.mark.parametrize("key", sorted(PINS))
def test_default_path_is_byte_identical(key):
    task_id, protocol = key
    result = build(BUNDLE[task_id], protocol, legacy_factory(BUNDLE[task_id]), seed=3).run()
    trace, config, metrics = PINS[key]
    assert (result.trace_hash, result.config_hash) == (trace, config)
    assert result.metrics == metrics


# ------------------------------------------------------------------ verify_claim
def view(task, ids=None):
    return dict(task, evidence=[e for e in task["evidence"] if ids is None or e["id"] in ids])


def choice_claim(**kw):
    e = MED["evidence"][0]
    quote = e["text"][10:60]
    return {"answer": "yes", "evidence_ids": [e["id"]], "brief": "b",
            "quotes": [{"evidence_id": e["id"], "text": quote}], **kw}


def calc_claim(answer="48.92", op="subtract", a="$ 148.92", b="$ 100.00", **kw):
    return {"answer": answer, "evidence_ids": ["table_1"], "brief": "b",
            "calculation": {"operation": op, "operands": [{"evidence_id": "table_1", "quote": a},
                                                          {"evidence_id": "table_1", "quote": b}]}, **kw}


def test_verbatim_quote_verifies_even_across_whitespace():
    assert verify_claim(choice_claim(), view(MED)).status == VERIFIED
    e = MED["evidence"][0]
    words = e["text"][10:60].split()
    spaced = "  \n ".join(words)
    claim = choice_claim(quotes=[{"evidence_id": e["id"], "text": spaced}])
    assert verify_claim(claim, view(MED)).status == VERIFIED


def test_quote_not_in_passage_fails_and_is_case_sensitive():
    e = MED["evidence"][0]
    bad = choice_claim(quotes=[{"evidence_id": e["id"], "text": "this sentence is certainly not present"}])
    verdict = verify_claim(bad, view(MED))
    assert verdict.status == FAILED and "verbatim" in verdict.reason
    swapped = choice_claim(quotes=[{"evidence_id": e["id"], "text": e["text"][10:60].swapcase()}])
    assert verify_claim(swapped, view(MED)).status == FAILED


def test_quote_from_uncited_or_invisible_passage_fails():
    first, second = MED["evidence"][0], MED["evidence"][1]
    uncited = choice_claim(quotes=[{"evidence_id": second["id"], "text": second["text"][10:60]}])
    assert "not cited" in verify_claim(uncited, view(MED)).reason
    sharded = view(MED, {first["id"]})  # the peer's passage is not visible to this agent
    claim = choice_claim(evidence_ids=[first["id"], second["id"]],
                         quotes=[{"evidence_id": second["id"], "text": second["text"][10:60]}])
    verdict = verify_claim(claim, sharded)
    assert verdict.status == FAILED and "not visible" in verdict.reason


def test_quote_shape_limits_fail():
    e = MED["evidence"][0]
    ok = {"evidence_id": e["id"], "text": e["text"][10:60]}
    assert verify_claim(choice_claim(quotes=[ok] * 4), view(MED)).status == FAILED
    assert verify_claim(choice_claim(quotes=[{"evidence_id": e["id"], "text": e["text"][10:15]}]), view(MED)).status == FAILED
    assert verify_claim(choice_claim(quotes=["nope"]), view(MED)).status == FAILED
    assert verify_claim(choice_claim(quotes="nope"), view(MED)).status == FAILED


def test_no_quotes_is_unverified_and_abstain_has_no_verdict():
    plain = {"answer": "yes", "evidence_ids": [MED["evidence"][0]["id"]], "brief": "b"}
    assert verify_claim(plain, view(MED)).status == UNVERIFIED
    assert verify_claim({**plain, "quotes": []}, view(MED)).status == UNVERIFIED
    assert verify_claim({"answer": None, "evidence_ids": [], "brief": ""}, view(MED)) is None


def test_calculation_verified_on_real_finance_task():
    verdict = verify_claim(calc_claim(), view(FIN))
    assert verdict.status == VERIFIED and verdict.checks["calculation"] == "pass"
    assert verify_claim(calc_claim(answer="48.920"), view(FIN)).status == VERIFIED  # numeric, not textual


def test_calculation_mismatch_and_malformed_fail():
    assert verify_claim(calc_claim(answer="49.00"), view(FIN)).status == FAILED
    assert verify_claim(calc_claim(a="$ 999.99"), view(FIN)).status == FAILED  # token not in the passage
    assert verify_claim(calc_claim(op="power"), view(FIN)).status == FAILED
    assert verify_claim({**calc_claim(), "calculation": "48.92"}, view(FIN)).status == FAILED
    bad = calc_claim()
    bad["calculation"]["operands"] = bad["calculation"]["operands"][:1]
    assert verify_claim(bad, view(FIN)).status == FAILED
    abstaining = calc_claim(op="abstain")
    abstaining["calculation"]["operands"] = []
    assert verify_claim(abstaining, view(FIN)).status == FAILED


def test_decimal_quotes_without_calculation_stay_unverified_but_bad_quotes_fail():
    e = FIN["evidence"][0]
    quoted = {"answer": "48.92", "evidence_ids": [e["id"]], "brief": "b",
              "quotes": [{"evidence_id": e["id"], "text": e["text"][:40]}]}
    assert verify_claim(quoted, view(FIN)).status == UNVERIFIED
    assert verify_claim({**calc_claim(), "quotes": [{"evidence_id": "table_1", "text": "no such text here"}]},
                        view(FIN)).status == FAILED


def test_verdict_is_label_blind():
    for claim, task in ((choice_claim(), MED), (calc_claim(), FIN), (calc_claim(answer="1.00"), FIN)):
        base = verify_claim(claim, view(task))
        changed = dict(view(task), expected_answer="zzz", tolerance="999")
        deleted = {k: v for k, v in view(task).items() if k not in ("expected_answer", "tolerance")}
        assert verify_claim(claim, changed) == base == verify_claim(claim, deleted)


# ------------------------------------------------------------------ prompts / policy
def test_verified_prompt_states_the_contract():
    choice = verified_claims_system(view(MED))
    assert "AT MOST 3" in choice and "verbatim" in choice and "quotes" in choice and '"yes"' in choice
    decimal = verified_claims_system(view(FIN))
    assert "AT MOST 3" in decimal and "calculation" in decimal and "exact source numeric token" in decimal
    assert choice.startswith(VERIFIED_CLAIMS_SYSTEM)
    policy = QAPolicy(FakeProvider(lambda r: "{}"), "m", claims="verified_claims_v1")
    assert policy.describe()["claims"] == "verified_claims_v1"
    assert "claims" not in QAPolicy(FakeProvider(lambda r: "{}"), "m").describe()
    assert "claims" not in ScriptedQAPolicy(lambda v: {}).describe()
    with pytest.raises(ValueError):
        ScriptedQAPolicy(lambda v: {}, claims="other")


# ------------------------------------------------------------------ world: admission
def claim_reply(task, answer_by_agent, *, claims="verified_claims_v1", lenient=False, extra=None):
    """Each agent quotes its first visible passage; `answer_by_agent` maps agent index to a reply override."""
    def make(agent):
        i = int(agent.rsplit("-", 1)[1]) - 1

        def reply(view_):
            e = view_.observation["task"]["evidence"][0]
            base = {"answer": "yes", "evidence_ids": [e["id"]], "brief": "b",
                    "quotes": [{"evidence_id": e["id"], "text": e["text"][10:60]}]}
            return {**base, **answer_by_agent.get(i, {}), **(extra or {})}

        return ScriptedQAPolicy(reply, claims=claims, lenient=lenient)

    return make


def run(task, protocol, factory, **world):
    return build(task, protocol, factory, seed=1, **world).run()


def test_two_witness_admission():
    one = {1: {"quotes": []}, 2: {"quotes": []}}  # only worker-1 stays verified
    solo = run(MED, "independent_vote", claim_reply(MED, one), verify=True, min_confirmations=2).metrics
    assert solo["admitted_answers"] == []
    assert solo["verification_counts"] == {"verified": 1, "unverified": 2, "failed": 0}
    pair = run(MED, "independent_vote", claim_reply(MED, {2: {"quotes": []}}), verify=True,
               min_confirmations=2).metrics
    assert pair["admitted_answers"] == ["yes"]
    single_witness = run(MED, "independent_vote", claim_reply(MED, one), verify=True).metrics
    assert single_witness["admitted_answers"] == ["yes"]  # min_confirmations=1 admits on sight


def test_disagreeing_verified_agents_do_not_pool():
    metrics = run(MED, "independent_vote", claim_reply(MED, {1: {"answer": "no"}}), verify=True,
                  min_confirmations=2).metrics
    assert metrics["admitted_answers"] == ["yes"]  # workers 1 and 3 agree; worker 2 stands alone
    assert [v["answer"] for v in metrics["votes"]] == ["yes", "no", "yes"]


def test_verify_metrics_keys_and_failed_claims():
    bad = {1: {"quotes": [{"evidence_id": "context_0", "text": "text that is not in the passage"}]}}
    metrics = run(MED, "independent_vote", claim_reply(MED, bad), verify=True).metrics
    assert metrics["verification_counts"] == {"verified": 2, "unverified": 0, "failed": 1}
    assert [(v["seat"], v["verification"]) for v in metrics["votes"]] == [
        ("worker-1", VERIFIED), ("worker-2", FAILED), ("worker-3", VERIFIED)]
    plain = run(MED, "independent_vote", claim_reply(MED, {})).metrics
    assert not {"votes", "verification_counts", "admitted_answers"} & set(plain)


def test_retraction_removes_a_changed_mind_from_admission():
    def make(agent):
        def reply(view_):
            e = view_.observation["task"]["evidence"][0]
            answer = "yes" if view_.observation["round"] == 0 else ("no" if agent.endswith("1") else "yes")
            return {"answer": answer, "evidence_ids": [e["id"]], "brief": "b",
                    "quotes": [{"evidence_id": e["id"], "text": e["text"][10:60]}]}
        return ScriptedQAPolicy(reply, claims="verified_claims_v1")

    sched = build(MED, "signal_board", make, seed=1, verify=True, min_confirmations=2)
    metrics = sched.run().metrics
    assert metrics["admitted_answers"] == ["yes"]  # worker-1's early yes was retracted, 2 and 3 still confirm
    assert metrics["votes"][0] == {"seat": "worker-1", "answer": "no", "verification": VERIFIED}


def test_board_claims_carry_the_verification_mark():
    sched = build(MED, "signal_board", claim_reply(MED, {0: {"quotes": []}}), seed=1, verify=True)
    sched.run()
    first_round = [e for e in sched.log.of_type(ev.SIGNAL_DEPOSITED) if e.tick == 1]
    assert {e.agent_id: e.data["payload"]["verification"] for e in first_round} == {
        "worker-1": UNVERIFIED, "worker-2": VERIFIED, "worker-3": VERIFIED}
    plain = build(MED, "signal_board", claim_reply(MED, {}, claims=None), seed=1)
    plain.run()
    assert all("verification" not in e.data["payload"] for e in plain.log.of_type(ev.SIGNAL_DEPOSITED))


def test_options_change_config_hash_only_when_set():
    base = ResearchQAWorld(MED, "independent_vote").describe()
    assert set(base) == {"world", "version", "task_id", "protocol"}
    on = ResearchQAWorld(MED, "independent_vote", verify=True, min_confirmations=2, lenient=True, plurality=True)
    assert {"verify", "min_confirmations", "lenient", "plurality"} <= set(on.describe())


def test_aggregator_consumes_votes_from_metrics():
    task = copy.deepcopy(MED)
    metrics = run(task, "independent_vote", claim_reply(task, {1: {"answer": "no", "quotes": []}}), verify=True,
                  min_confirmations=2).metrics
    votes = [Vote(v["seat"], v["seat"], v["answer"], v["verification"]) for v in metrics["votes"]]
    decision = Aggregator().decide(votes, choices=task["choices"])
    assert decision.answer == "yes" and not decision.abstained
    assert metrics["answer"] == "yes"


# ------------------------------------------------------------------ lenient / plurality
def test_lenient_truncates_and_drops_extras_recording_violations():
    ids = [e["id"] for e in MED["evidence"]]
    extra = {"evidence_ids": ids * 2 + ["context_0"], "confidence": 0.9}
    strict = run(MED, "independent_vote", claim_reply(MED, {}, claims=None, extra=extra))
    assert strict.metrics["status"] == "invalid" and strict.metrics["invalid"] == 3

    captured = []

    def factory(agent):
        inner = claim_reply(MED, {}, claims=None, lenient=True, extra=extra)(agent)
        decide = inner.decide
        inner.decide = lambda v: captured.append(decide(v)) or captured[-1]
        return inner

    lenient = run(MED, "independent_vote", factory, lenient=True).metrics
    assert lenient["status"] == "completed" and lenient["format_failures"] == 0 and lenient["invalid"] == 0
    assert captured[0].params["format_violations"] == ["unknown_keys:confidence,quotes", "evidence_ids_deduplicated"]
    assert len(captured[0].params["evidence_ids"]) <= 3


def test_lenient_format_failure_is_a_missing_vote_counted_separately():
    def broken(agent):
        i = int(agent.rsplit("-", 1)[1])
        return ScriptedQAPolicy(lambda v: {"answer": "yes", "evidence_ids": ["context_0"], "brief": "b"}
                                if i != 3 else {"answer": "maybe-not-a-choice", "evidence_ids": [], "brief": ""},
                                lenient=True)

    lenient = run(MED, "independent_vote", broken, lenient=True).metrics
    assert lenient["status"] == "completed" and lenient["answer"] == "yes"
    assert lenient["format_failures"] == 1 and lenient["invalid"] == 0 and lenient["final_answers"] == ["yes", "yes", None]
    strict = run(MED, "independent_vote", broken).metrics
    assert strict["status"] == "invalid" and "format_failures" not in strict


def test_lenient_non_json_is_malformed_not_repaired():
    from antelligence.worlds.research_qa.policies import parse_reply
    from backend.swarm_core import _PayloadError

    with pytest.raises(_PayloadError):
        parse_reply("not json at all", MED, None, True)
    with pytest.raises(_PayloadError):
        parse_reply('["answer"]', MED, None, True)


def test_plurality_control_reports_alongside_strict_majority():
    def votes(answers):
        return lambda agent: ScriptedQAPolicy(lambda v: {"answer": answers[int(agent[-1]) - 1],
                                                        "evidence_ids": [], "brief": ""})

    split = run(FIN, "independent_vote", votes(["48.92", "10", "48.920"]), plurality=True).metrics
    assert split["plurality_answer"] == "48.92" and split["plurality_correct"] is True  # 48.92 == 48.920
    spread = run(FIN, "independent_vote", votes(["48.92", "10", "11"]), plurality=True).metrics
    assert spread["answer"] is None and spread["plurality_answer"] is None  # three-way tie
    tie = run(MED, "independent_vote", votes(["yes", "no", None]), plurality=True).metrics
    assert tie["plurality_answer"] is None and tie["plurality_correct"] is None
    assert "plurality_answer" not in run(MED, "independent_vote", votes(["yes", "no", None])).metrics


def test_a_dropped_currency_sign_still_binds_but_percent_does_not():
    from antelligence.worlds.research_qa.verify import verify_claim

    task = {"answer_type": "decimal", "choices": [], "evidence": [
        {"id": "t", "text": '["2016 net revenue", "$ 644.2"] ["2015 net revenue", "$ 637.2"] ["margin", "5.0%"]'}]}

    def claim(a, b, answer, op="subtract"):
        return {"answer": answer, "evidence_ids": ["t"], "brief": "",
                "calculation": {"operation": op, "operands": [{"evidence_id": "t", "quote": a},
                                                               {"evidence_id": "t", "quote": b}]}}

    assert verify_claim(claim("644.2", "637.2", "7"), task).status == "verified"
    assert verify_claim(claim("$ 644.2", "$ 637.2", "7"), task).status == "verified"
    assert verify_claim(claim("644.2", "999.9", "7"), task).status == "failed"  # not in the source at all
    percent = {"answer": "5", "evidence_ids": ["t"], "brief": "",
               "calculation": {"operation": "identity", "operands": [{"evidence_id": "t", "quote": "5.0"}]}}
    assert verify_claim(percent, task).status == "failed"  # a dropped % is not restored
    percent["calculation"]["operands"][0]["quote"] = "5.0%"
    assert verify_claim(percent, task).status == "verified"
