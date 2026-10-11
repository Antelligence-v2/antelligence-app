import json
import re
from pathlib import Path

import pytest

from antelligence.experiments.pilot_contract import CONDITIONS, PilotWorld
from antelligence.kernel import Intent, LocalView
from antelligence.kernel.decision import MAX_CHECKS, SensedState
from antelligence.kernel.field import GridField
from antelligence.kernel.scheduler import RunConfig, Scheduler
from antelligence.worlds.graph_coloring import GRAPH_COLORING, ColoringSensor, GraphColoringWorld, parse_colour_action
from antelligence.worlds.graph_coloring import scripts
from antelligence.worlds.graph_coloring.graphs import FAMILIES, Graph, family_for_seed, make_graph
from antelligence.worlds.graph_coloring.variants import DEV_SEEDS, validity_check
from antelligence.worlds.graph_coloring.world import DROP_P, LIAR_ID, ROUNDS

SENSOR = ColoringSensor()
TRIANGLE_TAIL = Graph("ws", 4, ((0, 1), (0, 2), (1, 2), (2, 3)), ((0.0, 0.0),) * 4)  # palette 4


class AlwaysAnnounce:
    """Takes colour_1 every round: maximum message traffic, for drop-rate statistics."""

    def describe(self):
        return {"policy": "always"}

    def decide(self, view):
        return Intent("colour_1")


def play(seed, condition, policy, **kw):
    world = GraphColoringWorld(seed, condition, **kw)
    result = Scheduler(world, {}, GridField(), RunConfig(f"t-{condition}-{seed}", seed=seed, max_ticks=10),
                       default_policy=policy).run()
    return world, result


def view_of(world, agent, tick):
    return LocalView(agent, tick, world.revision, 0, world.observe(agent, tick).data)


# --- graphs -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("family", FAMILIES)
def test_generators_are_seeded_connected_and_sized(family):
    for seed in (1, 2, 3, 100, 101):
        g = make_graph(family, 8, seed)
        assert g == make_graph(family, 8, seed) and g.n == 8 and len(g.positions) == 8
        assert all(0 <= u < v < 8 for u, v in g.edges) and len(set(g.edges)) == len(g.edges)
        assert all(g.neighbours()[i] for i in range(8))
    assert len({make_graph(family, 8, s).edges for s in range(20)}) > 5  # seeds really change the graph


def test_family_round_robin_and_palette_is_max_degree_plus_one():
    assert [family_for_seed(s) for s in (3, 4, 5)] == ["ws", "ba", "dt"]
    for seed in range(1, 25):
        world = GraphColoringWorld(seed)
        assert world.palette == world.graph.max_degree + 1 <= 8
        assert len(world.agents()) == 8 and len(world.target) == 8
        assert world.score() == 0.0 and GraphColoringWorld(seed).graph == world.graph  # nobody coloured yet


def test_graph_is_the_same_in_every_condition():
    assert len({GraphColoringWorld(101, c).graph.edges for c in CONDITIONS}) == 1


# --- typed answers --------------------------------------------------------------------------------------------
def test_typed_actions_are_exact_never_prefix_matched():
    assert parse_colour_action("colour_1", 12) == 0 and parse_colour_action("colour_10", 12) == 9
    assert parse_colour_action("colour_12", 12) == 11 and parse_colour_action("colour_13", 12) is None
    for bad in ("Group 10", "colour_", "colour_1 ", "COLOUR_1", "colour_0", "red", ""):
        assert parse_colour_action(bad, 12) is None


def test_apply_accepts_noop_and_rejects_unknown_or_out_of_palette():
    world = GraphColoringWorld(101)
    assert world.apply("0", Intent("noop"), 1).accepted and world.colour["0"] is None
    assert world.apply("0", Intent("colour_2"), 1).accepted and world.colour["0"] == 1
    assert world.apply("0", Intent("noop"), 2).accepted and world.colour["0"] == 1  # noop keeps the colour
    for bad in ("colour_99", "Group 1", "colour_01"):
        assert not world.apply("0", Intent(bad), 2).accepted
    assert world.colour["0"] == 1 and world.counters["invalid_actions"] == 3


# --- scorer ---------------------------------------------------------------------------------------------------
def test_score_is_exact_on_a_hand_built_graph():
    world = GraphColoringWorld(1, graph=TRIANGLE_TAIL)
    assert world.palette == 4 and world.score() == 0.0
    for agent, colour in (("0", 0), ("1", 1), ("2", 0), ("3", 1)):  # edge (0,2) clashes, three of four proper
        world.colour[agent] = colour
    assert world.score() == 0.75 and world.conflicts() == 1
    world.colour["2"] = 2
    assert world.score() == 1.0
    world.colour["3"] = None  # an agent with no colour leaves its edge improper
    assert world.score() == 0.75


def test_v2_score_excludes_edges_touching_the_liar():
    world = GraphColoringWorld(1, "v2", graph=TRIANGLE_TAIL, liar="2")
    assert world.scored_edges() == [("0", "1")]
    world.colour.update({"0": 0, "1": 1, "2": 0, "3": 0})  # every liar edge clashes, the honest edge is fine
    assert world.score() == 1.0
    world.colour["1"] = 0
    assert world.score() == 0.0
    assert GraphColoringWorld(1, "base", graph=TRIANGLE_TAIL).liar is None


# --- round rule and messages --------------------------------------------------------------------------------
def test_round_rule_messages_arrive_one_round_later_and_final_answer_after_last_round():
    world = GraphColoringWorld(1, graph=TRIANGLE_TAIL)
    assert world.rounds == ROUNDS == 4 and not world.done(3) and world.done(4)
    assert all(h["colour"] is None for h in world.observe("2", 1).data["heard"].values())  # round 1: nothing heard
    world.apply("0", Intent("colour_3"), 1)
    assert world.observe("2", 1).data["heard"]["0"]["colour"] is None  # not seen in the round it was sent
    world.step_environment(1)
    heard = world.observe("2", 2).data["heard"]["0"]
    assert heard["colour"] == 2 and heard["fresh"] and heard["round"] == 1
    world.step_environment(2)  # agent 0 stayed silent in round 2: remembered, no longer fresh
    heard = world.observe("2", 3).data["heard"]["0"]
    assert heard["colour"] == 2 and not heard["fresh"]
    assert world.observe("1", 3).data["heard"]["0"]["colour"] == 2 and "1" not in world.fresh["0"]


def test_acknowledgement_carries_the_last_heard_colour():
    world = GraphColoringWorld(1, graph=TRIANGLE_TAIL)
    world.apply("0", Intent("colour_1"), 1)
    world.step_environment(1)
    world.apply("1", Intent("colour_2"), 2)
    world.step_environment(2)
    msg = world.observe("0", 3).data["heard"]["1"]
    assert msg["colour"] == 1 and msg["ack"] == 0  # agent 1 tells agent 0 it heard colour_1


def test_lost_message_rate_is_about_thirty_percent_and_seeded():
    sent = dropped = 0
    for seed in range(200, 240):
        world, _ = play(seed, "v1", AlwaysAnnounce())
        sent, dropped = sent + world.counters["sent"], dropped + world.counters["dropped"]
    assert sent > 2000 and abs(dropped / sent - DROP_P) < 0.03
    a, _ = play(7, "v1", AlwaysAnnounce())
    b, _ = play(7, "v1", AlwaysAnnounce())
    assert a.counters == b.counters and play(7, "base", AlwaysAnnounce())[0].counters["dropped"] == 0


def test_liar_reports_random_colours_and_honest_agents_do_not():
    world = GraphColoringWorld(1, "v2", graph=TRIANGLE_TAIL, liar="2")
    liar_reports = set()
    for tick in range(1, 40):
        world.apply("0", Intent("colour_1"), tick)  # honest agent 0 always says colour_1
        world.apply("2", Intent("colour_1"), tick)  # the liar's real colour is also colour_1
        world.step_environment(tick)
        assert world.observe("1", tick + 1).data["heard"]["0"]["colour"] == 0
        liar_reports.add(world.observe("1", tick + 1).data["heard"]["2"]["colour"])
    assert len(liar_reports) >= 3 and world.counters["lied"] == 39 * 3
    world.colour["2"] = None  # a liar chatters even when it holds no colour
    world.step_environment(40)
    assert world.observe("3", 41).data["heard"]["2"]["fresh"]


# --- determinism ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("condition", CONDITIONS)
def test_scheduler_trace_hash_is_deterministic(condition):
    pol = GRAPH_COLORING.script(condition, adapted=condition != "base")
    first = play(101, condition, pol)[1]
    again = play(101, condition, GRAPH_COLORING.script(condition, adapted=condition != "base"))[1]
    other = play(102, condition, pol)[1]
    assert first.trace_hash == again.trace_hash != other.trace_hash and first.ticks == ROUNDS
    assert first.metrics == again.metrics


def test_replay_frames_expose_scene_and_snapshot():
    world = GraphColoringWorld(101)
    sched = Scheduler(world, {}, GridField(), RunConfig("f", seed=101, max_ticks=10),
                      default_policy=GRAPH_COLORING.script("base", adapted=False))
    sched.run()
    scene = sched.scene
    assert scene["kind"] == "graph" and len(scene["nodes"]) == 8 and len(scene["colours"]) == world.palette
    assert len(sched.frames) == ROUNDS + 1
    last = sched.frames[-1]["world"]
    assert len(last["colours"]) == 8 and last["conflicts"] == world.conflicts()
    json.dumps(sched.frames)


# --- sensor ---------------------------------------------------------------------------------------------------
def test_sensor_text_is_short_words_and_actions_are_typed():
    world, _ = play(101, "base", GRAPH_COLORING.script("base", adapted=False))
    for agent in world.agents():
        state = SENSOR.sense(view_of(world, agent, 4))
        assert isinstance(state, SensedState) and len(state.text) < 420
        assert "Round 4 of 4" in state.text and "Your colour:" in state.text
        assert not re.search(r"colour_\d", state.text) and len(state.checks) <= MAX_CHECKS
        assert set(state.actions) == {"noop", *(f"colour_{i + 1}" for i in range(world.palette))}


def test_sensor_text_example_and_code_side_counting():
    world = GraphColoringWorld(1, graph=TRIANGLE_TAIL)
    world.apply("0", Intent("colour_1"), 1)
    world.apply("1", Intent("colour_2"), 1)
    world.apply("2", Intent("colour_1"), 1)
    world.step_environment(1)
    world.apply("2", Intent("noop"), 2)
    state = SENSOR.sense(view_of(world, "2", 2))
    assert state.text == ("Your colour: red. Neighbours: agent 0 said red (same as yours), agent 1 said blue, "
                          "agent 3 sent nothing this round. Colours your neighbours use: red, blue. "
                          "Colours available: red, blue, green, yellow. Round 2 of 4.")
    assert state.fields["same"] == ["0"] and state.fields["silent"] == ["3"] and state.fields["free"] == [2, 3]
    assert set(state.checks) == {"heard_all"}
    first = SENSOR.sense(view_of(world, "3", 1))
    assert "none yet" in first.text and "Nothing heard yet" in first.text and not first.checks


def test_flipping_reports_raise_the_honesty_check():
    world = GraphColoringWorld(1, "v2", graph=TRIANGLE_TAIL, liar="2")
    for tick in range(1, 6):
        world.step_environment(tick)
        state = SENSOR.sense(view_of(world, "3", tick + 1))
        if state.fields["flipped"]:
            assert "reports_true" in state.checks and "was" in state.text
            return
    pytest.fail("a chattering liar never flipped its report")


# --- scripts --------------------------------------------------------------------------------------------------
def test_S_waits_for_lower_neighbours_colours_then_takes_lowest_free_colour():
    world = GraphColoringWorld(1, graph=TRIANGLE_TAIL)
    s = scripts.PatientGreedy(SENSOR)
    assert s.decide(view_of(world, "0", 1)).action == "colour_1"  # no lower neighbour: colours at once
    assert s.decide(view_of(world, "2", 1)).action == "noop"  # waits for agents 0 and 1
    world.apply("0", Intent("colour_1"), 1)
    world.apply("1", Intent("colour_2"), 1)
    world.step_environment(1)
    assert s.decide(view_of(world, "2", 2)).action == "colour_3"
    world.colour["2"] = 2
    assert s.decide(view_of(world, "2", 3)).action == "noop"  # coloured once, never changes


def test_S_never_guesses_but_S_prime_v1_does_and_resends():
    world = GraphColoringWorld(1, graph=TRIANGLE_TAIL)
    s, sp = scripts.PatientGreedy(SENSOR), GRAPH_COLORING.script("v1", adapted=True)
    last = view_of(world, "2", 4)
    assert s.decide(last).action == "noop" and sp.decide(last).action == "colour_1"
    world.apply("0", Intent("colour_1"), 1)
    assert sp.decide(view_of(world, "0", 2)).action == "colour_1"  # nobody acknowledged: resend
    world.step_environment(1)
    world.apply("1", Intent("colour_2"), 2)
    world.apply("2", Intent("colour_3"), 2)
    world.step_environment(2)
    assert world.observe("0", 3).data["heard"]["1"]["ack"] == 0
    acked = view_of(world, "0", 3)
    assert sp.decide(acked).action == "noop" and s.decide(acked).action == "noop"  # both neighbours acknowledged


def test_S_prime_v2_ignores_the_liar_while_S_waits_on_its_shifting_reports():
    world = GraphColoringWorld(1, "v2", graph=TRIANGLE_TAIL)  # the liar is agent 1
    for tick in range(1, 4):
        world.apply("0", Intent("colour_2"), tick)
        world.step_environment(tick)
    view = view_of(world, "2", 4)
    assert view.observation["heard"]["1"]["colour"] is not None
    sp, s = GRAPH_COLORING.script("v2", adapted=True), GRAPH_COLORING.script("v2", adapted=False)
    assert isinstance(sp, scripts.IgnoreLiar) and sp.ignore == LIAR_ID == "1"
    assert sp.decide(view).action == "colour_1"  # liar ignored; honest agent 0 holds colour_2
    assert s.decide(view).action == "noop"  # S keeps waiting: the liar's report keeps changing


# --- pilot contract -------------------------------------------------------------------------------------------
def test_pilot_world_contract():
    assert isinstance(GRAPH_COLORING, PilotWorld) and GRAPH_COLORING.name == "graph_coloring"
    assert "noop" in GRAPH_COLORING.actions and "colour_8" in GRAPH_COLORING.actions
    world = GRAPH_COLORING.make_world(101, "v1")
    assert GRAPH_COLORING.groups(world) == {"g1": ("0", "1", "2", "3"), "g2": ("4", "5", "6", "7")}
    summary = GRAPH_COLORING.board_summary(world, 0)
    assert summary.counts["conflicts_left"] == len(world.scored_edges()) and summary.counts["uncoloured"] == 8
    with pytest.raises(ValueError):
        GRAPH_COLORING.script("base", adapted=True)
    with pytest.raises(ValueError):
        GRAPH_COLORING.make_world(101, "v9")


def test_oracle_and_labelled_questions():
    world, _ = play(101, "base", scripts.PatientGreedy(SENSOR))
    clean = GraphColoringWorld(101)
    clean.colour.update(clean.target)
    assert all(GRAPH_COLORING.oracle_action(clean, a, 1) == "noop" for a in clean.agents())
    clean.colour["7"] = None
    assert GRAPH_COLORING.oracle_action(clean, "7", 1) == f"colour_{clean.target['7'] + 1}"
    for tick in (1, 4):
        for agent in world.agents():
            qs = GRAPH_COLORING.labelled_questions(world, view_of(world, agent, tick), tick)
            assert qs[-1].qid == "move" and qs[-1].kind == "move" and len(qs) <= 3
            assert [q.kind for q in qs[:-1]] == ["judgement"] * (len(qs) - 1)
            assert qs[-1].label in qs[-1].question.options
    liar = GraphColoringWorld(101, "v2")
    liar.step_environment(1)
    nbr = liar.neighbours(LIAR_ID)[0]
    labels = {q.qid: q.label for q in GRAPH_COLORING.labelled_questions(liar, view_of(liar, nbr, 2), 2)}
    assert labels["heard_all"] is (len(liar.neighbours(nbr)) == 1)  # only the chattering liar spoke in round 1


# --- validity -------------------------------------------------------------------------------------------------
def test_oracle_actions_lists_every_colour_no_neighbour_holds():
    world = GraphColoringWorld(1, graph=TRIANGLE_TAIL)  # 2 touches 0, 1 and 3; palette of 4
    assert GRAPH_COLORING.oracle_actions(world, "2", 1) == tuple(f"colour_{i}" for i in (1, 2, 3, 4))  # nobody coloured
    world.colour.update({"0": 0, "1": 1, "3": 1})
    assert GRAPH_COLORING.oracle_actions(world, "2", 1) == ("colour_3", "colour_4")  # uncoloured: free colours
    world.colour["2"] = 0  # clashes with 0
    assert GRAPH_COLORING.oracle_actions(world, "2", 1) == ("colour_3", "colour_4")
    assert GRAPH_COLORING.oracle_action(world, "2", 1) == "colour_3"
    world.colour["2"] = 2  # clashes with nobody
    assert GRAPH_COLORING.oracle_actions(world, "2", 1) == ("noop",)
    world.colour.update({"0": 0, "1": 1, "3": 2, "2": 0})  # every colour held around 2 -> reference colour
    world.palette = 3
    assert GRAPH_COLORING.oracle_actions(world, "2", 1) == (f"colour_{world.target['2'] + 1}",)
    world.palette = 4
    world.colour["2"] = None
    view = view_of(world, "2", 1)
    move = GRAPH_COLORING.labelled_questions(world, view, 1)[-1]
    assert move.accept == GRAPH_COLORING.oracle_actions(world, "2", 1) and move.label == move.accept[0]


def test_validity_check_on_dev_seeds_passes_both_variants(tmp_path):
    result = validity_check(DEV_SEEDS)
    assert result["seeds"] == list(range(100, 110)) and result["all_pass"]
    for variant in ("v1", "v2"):
        v = result["variants"][variant]
        assert v["score_Sprime_base"] >= 0.9 * v["score_S_base"]
        assert v["score_S_variant"] <= 0.5 * v["score_Sprime_variant"]
    path = Path(__file__).resolve().parents[2] / "docs/research/v4-pilot-20261011/validity-graph_coloring.json"
    assert json.loads(path.read_text())["variants"]["v1"]["pass"]  # the committed record matches


def test_kernel_never_imports_a_world():
    kernel = Path(__file__).resolve().parents[2] / "antelligence/kernel"
    for source in kernel.rglob("*.py"):
        assert not re.search(r"^\s*(from|import)\s+antelligence\.worlds", source.read_text(), re.M), source


def test_describe_declares_episode_length():
    from antelligence.worlds.graph_coloring import GRAPH_COLORING
    from antelligence.worlds.graph_coloring.world import ROUNDS
    assert GRAPH_COLORING.describe()["max_ticks"] == ROUNDS
