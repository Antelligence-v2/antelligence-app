"""foraging_sb: SwarmBench foraging port (layouts, view, messages, push rule, variants, S/S', sensor, PilotWorld)."""

import asyncio
import json
import re
from pathlib import Path
from random import Random

import pytest

from antelligence.experiments.pilot_contract import PilotWorld
from antelligence.kernel import Intent, LocalView
from antelligence.kernel.decision import REPORT, SensedState, Sensor
from antelligence.kernel.field import GridField
from antelligence.kernel.scheduler import RunConfig, Scheduler
from antelligence.worlds.foraging_sb import ACTIONS, FORAGING_SB, ForagingSBWorld, ForagingSensor, make_layout
from antelligence.worlds.foraging_sb.variants import DEV_SEEDS, RESULT, run_episode, validity_check
from antelligence.worlds.foraging_sb.world import (
    MSG_MAX,
    MSG_RADIUS,
    V1_PICKUPS,
    V2_FLIP_TICK,
    WIDTH,
)

ROOT = Path(__file__).resolve().parents[2]


def run(seed, condition="base", *, adapted=False, frames=True):
    world = FORAGING_SB.make_world(seed, condition)
    config = RunConfig(f"t-{condition}-{seed}", seed=seed, max_ticks=100, arm="S")
    sched = Scheduler(world, {}, GridField(), config, default_policy=FORAGING_SB.script(condition, adapted=adapted),
                      record_frames=frames)
    return sched, sched.run(), world


def place(world, **positions):
    for agent, pos in positions.items():
        world.positions[agent[1:]] = pos


def next_to(world, cells):
    """Free cells that share an edge with any of ``cells``, in a stable order."""
    around = [(c[0] + dx, c[1] + dy) for c in cells for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    return sorted({c for c in around if world._free(c)})


def lone(seed=101):
    """A world with the ten agents parked out of the way along the top row, for hand-built scenes."""
    world = ForagingSBWorld(seed)
    for i, a in enumerate(world.agents()):
        world.positions[a] = (-10 - i, -10)  # off-map: never touches anything
    return world


# --- layouts ----------------------------------------------------------------


@pytest.mark.parametrize("seed", DEV_SEEDS)
def test_layout_follows_the_swarmbench_draws(seed):
    lay = make_layout(seed)
    rng = Random(seed)  # same draws, same order as swarmbench/task.py Foraging.reset
    food_i, food_j = rng.choice([1, 7]), rng.choice([1, 7])
    horizontal = rng.randint(0, 1) == 0
    assert lay["horizontal"] == horizontal
    if horizontal:
        assert lay["food"][0] == (1, food_i)  # one wall -> odd count -> food and nest forced to column 1
    else:
        assert lay["food"][0] == (food_j, 1)
    assert len(lay["walls"]) == 36 + 6  # border plus one serpentine wall joining it (7 cells, 1 on the border)
    blocks = set(lay["food"]) | set(lay["nest"])
    assert len(lay["food"]) == len(lay["nest"]) == 4 and len(blocks) == 8 and not blocks & lay["walls"]
    starts = lay["starts"]
    assert len(starts) == len(set(starts)) == 10 and not set(starts) & (blocks | lay["walls"])


def test_all_four_published_layouts_occur():
    seen = {(make_layout(s)["horizontal"], make_layout(s)["food"][0]) for s in range(100, 140)}
    assert len(seen) == 4


# --- determinism, frames, contract -------------------------------------------


@pytest.mark.parametrize("condition", ["base", "v1", "v2"])
def test_same_seed_same_trace_hash(condition):
    a, b = run(101, condition, adapted=condition != "base")[1], run(101, condition, adapted=condition != "base")[1]
    assert a.trace_hash == b.trace_hash and a.config_hash == b.config_hash
    assert a.trace_hash != run(102, condition, adapted=condition != "base")[1].trace_hash


def test_replay_frames_are_recorded_and_outside_the_trace():
    sched, result, world = run(101)
    assert [f["tick"] for f in sched.frames] == list(range(0, 101))
    assert sched.scene["kind"] == "grid" and sched.scene["walls"] and sched.scene["nest"]
    last = sched.frames[-1]["world"]
    assert len(last["agents"]) == 10 and last["delivered"] == world.deliveries and len(last["food"]) == 4
    assert run(101, frames=False)[1].trace_hash == result.trace_hash


def test_pilot_world_contract_and_actions():
    assert isinstance(FORAGING_SB, PilotWorld) and isinstance(FORAGING_SB.sensor(), Sensor)
    assert REPORT not in FORAGING_SB.actions and 3 <= len(FORAGING_SB.actions) <= 8
    assert set(FORAGING_SB.actions) == {"north", "east", "south", "west", "pick_up", "drop", "stay"}
    world = FORAGING_SB.make_world(100, "base")
    groups = FORAGING_SB.groups(world)
    assert set(groups) == {"g1", "g2"} and [len(g) for g in groups.values()] == [5, 5]
    assert sorted(a for g in groups.values() for a in g) == world.agents()
    assert FORAGING_SB.describe()["world"] == "foraging_sb"
    with pytest.raises(ValueError):
        FORAGING_SB.make_world(100, "v3")
    with pytest.raises(ValueError):
        FORAGING_SB.script("base", adapted=True)


def test_every_agent_accepts_noop_and_stay():
    world = FORAGING_SB.make_world(100, "base")
    for a in world.agents():
        assert world.apply(a, Intent("noop"), 1).accepted and world.apply(a, Intent("stay"), 1).accepted
    assert not world.apply("0", Intent("teleport"), 1).accepted


# --- view, messages ----------------------------------------------------------


def test_view_is_egocentric_5x5_and_matches_the_world():
    world = FORAGING_SB.make_world(100, "base")
    for a in world.agents():
        obs = world.observe(a, 1).data
        rows = obs["view"]
        assert len(rows) == 5 and all(len(r) == 5 for r in rows) and rows[2][2] == "Y"
        px, py = obs["pos"]
        for r in range(5):
            for c in range(5):
                x, y = px + c - 2, py + r - 2
                ch = rows[r][c]
                if not (0 <= x < 10 and 0 <= y < 10):
                    assert ch == "*"
                elif (x, y) in world.walls:
                    assert ch == "W"
                elif (x, y) in world.food:
                    assert ch == "F"
                elif (x, y) in world.nest:
                    assert ch == "N"
    assert "walls" not in world.observe("0", 1).data  # no global map leaks into the observation


def test_messages_are_short_radius_limited_and_auto_generated():
    world = lone()
    food = world.food[0]
    sender_pos = (food[0] - 2, food[1] + 1) if food[0] > 2 else (food[0] + 2, food[1] + 1)
    place(world, a0=sender_pos, a1=(sender_pos[0], sender_pos[1] + 1), a2=(sender_pos[0] + 6, sender_pos[1] - 3))
    for a in ("0", "1", "2"):
        world.observe(a, 1)
    world.step_environment(1)
    assert world.messages_sent >= 1
    heard1 = world.observe("1", 2).data["heard"]
    assert [m["from"] for m in heard1] == ["0"] and re.fullmatch(r"food is [a-z-]+ of me", heard1[0]["text"])
    assert len(heard1[0]["text"]) <= MSG_MAX
    far = max(abs(sender_pos[0] + 6 - sender_pos[0]), 3)
    assert far > MSG_RADIUS and world.observe("2", 2).data["heard"] == []


def test_every_message_in_a_full_run_respects_length_and_radius():
    world = FORAGING_SB.make_world(104, "base")
    sched = Scheduler(world, {}, GridField(), RunConfig("m", seed=104, max_ticks=100, arm="S"),
                      default_policy=FORAGING_SB.script("base", adapted=False), record_frames=False)
    heard = []
    real = world.observe

    def spy(agent, tick):
        obs = real(agent, tick)
        heard.extend(obs.data["heard"])
        return obs

    world.observe = spy
    sched.run()
    assert world.messages_sent > 20 and heard
    assert all(len(m["text"]) <= MSG_MAX and max(abs(m["dx"]), abs(m["dy"])) <= MSG_RADIUS for m in heard)


# --- push rule and pick up / drop --------------------------------------------


def test_push_rule():
    world = lone(103)
    row = next(y for y in range(1, 9) if all(world._free((x, y)) for x in range(3, 9)))
    place(world, a0=(3, row), a1=(4, row), a2=(5, row), a3=(6, row))
    # three agents in a row in front of the mover: more than force 2 can shove
    out = world.apply("0", Intent("east"), 1)
    assert not out.accepted and out.reason == "blocked_by_agent" and world.positions["0"] == (3, row)
    # a chain of two moves together when the cell behind it is free
    place(world, a3=(-13, -10))
    out = world.apply("0", Intent("east"), 2)
    assert out.accepted and out.effects["pushed"] == 2
    assert [world.positions[a] for a in "012"] == [(4, row), (5, row), (6, row)]
    # one agent pushed
    place(world, a2=(-12, -10))
    assert world.apply("0", Intent("east"), 3).effects["pushed"] == 1
    assert [world.positions[a] for a in "01"] == [(5, row), (6, row)]
    # a pushed agent cannot be shoved into a wall
    place(world, a0=(7, row), a1=(8, row))
    out = world.apply("0", Intent("east"), 4)
    assert not out.accepted and out.reason == "blocked_by_agent" and world.positions["1"] == (8, row)
    assert world.stuck["0"] == 1  # the failed move is reported back to the agent


def test_walls_food_and_nest_never_move_or_admit_agents():
    world = lone()
    spot = next_to(world, world.nest)[0]
    nest_cell = next(c for c in world.nest if abs(c[0] - spot[0]) + abs(c[1] - spot[1]) == 1)
    step = (nest_cell[0] - spot[0], nest_cell[1] - spot[1])
    toward = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}[step]
    place(world, a0=spot)
    out = world.apply("0", Intent(toward), 1)
    assert not out.accepted and out.reason == "blocked" and world.positions["0"] == spot
    place(world, a1=(1, 1) if (1, 1) not in world.nest else (8, 8))  # a corner of the map: walls on two sides
    edge = world.positions["1"]
    assert not world.apply("1", Intent("north" if edge[1] == 1 else "south"), 1).accepted


def test_pick_up_and_drop_score_a_delivery():
    world = lone()
    spot, nspot = next_to(world, world.food)[0], next_to(world, world.nest)[0]
    place(world, a0=nspot)
    assert not world.apply("0", Intent("pick_up"), 1).accepted and not world.apply("0", Intent("drop"), 1).accepted
    place(world, a0=spot)
    assert not world.apply("0", Intent("drop"), 2).accepted
    assert world.apply("0", Intent("pick_up"), 3).accepted and world.carrying["0"]
    assert not world.apply("0", Intent("pick_up"), 3).accepted  # one piece at a time
    assert world.memory["0"].food_at is not None
    place(world, a0=nspot)
    assert world.apply("0", Intent("drop"), 4).accepted and world.deliveries == 1 and not world.carrying["0"]
    assert FORAGING_SB.score(world) == 1.0


# --- variants ----------------------------------------------------------------


def test_v1_patch_empties_after_n_pickups_and_a_new_one_appears():
    world = FORAGING_SB.make_world(100, "v1")
    old = list(world.food)
    spots = next_to(world, old)
    for i in range(V1_PICKUPS):
        world.carrying[str(i)] = False
        world.positions[str(i)] = spots[i % len(spots)]
        assert world.apply(str(i), Intent("pick_up"), i + 1).accepted
        assert (world.patch_swaps == 1) == (i + 1 == V1_PICKUPS)
    assert world.food != old and not set(world.food) & (world.walls | set(world.nest) | set(old))
    world.positions["9"] = spots[0]
    assert not world.apply("9", Intent("pick_up"), 99).accepted  # the old spot is empty
    base = FORAGING_SB.make_world(100, "base")
    base.carrying.update({a: False for a in base.agents()})
    for i in range(V1_PICKUPS + 1):
        base.carrying["0"] = False
        base.positions["0"] = spots[0]
        base.apply("0", Intent("pick_up"), i)
    assert base.patch_swaps == 0


def test_v2_mirrors_only_what_is_sensed_from_tick_t():
    world = FORAGING_SB.make_world(100, "v2")
    plain = FORAGING_SB.make_world(100, "base")
    a = next(a for a in world.agents() if world.view_rows(a, 1) != [r[::-1] for r in world.view_rows(a, 1)])
    assert world.view_rows(a, V2_FLIP_TICK - 1) == plain.view_rows(a, V2_FLIP_TICK - 1)
    assert world.view_rows(a, V2_FLIP_TICK) == [r[::-1] for r in plain.view_rows(a, V2_FLIP_TICK)]
    assert world.positions == plain.positions and world.walls == plain.walls  # the world itself is not mirrored
    assert plain.view_rows(a, 99) == plain.view_rows(a, 1)  # base never flips


# --- scripts -----------------------------------------------------------------


def test_s_trusts_its_memory_and_s_prime_v1_leaves_the_empty_spot():
    s_score = run_episode(100, "v1").extra["score"]
    sp_score = run_episode(100, "v1", adapted=True).extra["score"]
    assert sp_score >= 2 * s_score
    sched, _, world = run(100, "v1")
    assert world.counters["invalid"] > 100  # S keeps trying to pick up from the emptied spot


def test_s_prime_v2_beats_s_on_the_flipped_sensor_and_keeps_up_on_base():
    assert run_episode(100, "v2", adapted=True).extra["score"] >= 2 * run_episode(100, "v2").extra["score"]
    kept = run_episode(100, "base", variant="v2", adapted=True).extra["score"]
    assert kept >= 0.8 * run_episode(100, "base").extra["score"]


def test_scripts_read_the_sensed_fields_and_describe_themselves():
    for cond, adapted in (("base", False), ("v1", True), ("v2", True)):
        policy = FORAGING_SB.script(cond, adapted=adapted)
        assert policy.describe()["policy"].startswith("foraging_sb.")
        world = FORAGING_SB.make_world(100, cond)
        view = LocalView("0", 1, 0, 7, world.observe("0", 1).data)
        assert policy.decide(view).action in ACTIONS


# --- sensor ------------------------------------------------------------------


def midgame(condition):
    sched, _, world = run(101, condition, frames=False)
    return world


@pytest.mark.parametrize("condition", ["base", "v1", "v2"])
def test_sensor_text_is_short_words_with_at_most_two_noul_checks(condition):
    world = midgame(condition)
    sensor = FORAGING_SB.sensor()
    for a in world.agents():
        view = LocalView(a, 100, 0, 5, world.observe(a, 100).data)
        sensed = sensor.sense(view)
        assert isinstance(sensed, SensedState) and sensed == sensor.sense(view)  # deterministic
        assert len(sensed.text) <= 600 and len(sensed.text) < 1200  # ~150 tokens; the 300-token target is 1,200 chars
        assert not re.search(r"\(\s*-?\d+\s*,\s*-?\d+\s*\)", sensed.text)  # no coordinate pairs, words not raw numbers
        assert set(sensed.actions) == set(ACTIONS) and REPORT not in sensed.actions
        assert len(sensed.checks) <= 2 and all(q.type == "noul" for q in sensed.checks.values())
        assert sensed.fields["route"] in ACTIONS


def test_sensor_text_example_shape():
    world = FORAGING_SB.make_world(100, "base")
    text = ForagingSensor().sense(LocalView("0", 1, 0, 1, world.observe("0", 1).data)).text
    assert text.startswith("Carrying food: no. Remembered food spot: ") and "Remembered nest: " in text
    assert text.endswith(".") and "next step" not in text  # describes, never prescribes a move


def test_nest_check_flags_a_flipped_view():
    world = FORAGING_SB.make_world(100, "v2")
    for a in world.agents():
        obs = world.observe(a, V2_FLIP_TICK).data
        sensed = ForagingSensor().sense(LocalView(a, V2_FLIP_TICK, 0, 1, obs))
        if sensed.fields["nest_moved"]:
            assert "not where it was remembered" in sensed.text
            return
    # no agent had the nest in view at that moment: move one next to the nest and look again
    spot = next_to(world, world.nest)[0]
    nest = next(c for c in world.nest if abs(c[0] - spot[0]) + abs(c[1] - spot[1]) == 1)
    world.memory["0"].nest_at = (2 * spot[0] - nest[0], nest[1]) if nest[0] != spot[0] else (spot[0], 9)
    world.positions["0"] = spot
    sensed = ForagingSensor().sense(LocalView("0", 40, 0, 1, world.observe("0", 40).data))
    assert sensed.fields["nest_seen"] is not None


# --- labels, oracle, board ---------------------------------------------------


def test_labelled_questions_oracle_and_board_summary():
    sched, result, world = run(100, "v1", frames=False)
    summary = FORAGING_SB.board_summary(world, 100)
    assert summary.tick == 100 and summary.counts["deliveries"] == world.deliveries
    assert set(summary.counts) == {"deliveries", "carrying", "recent_deliveries"}
    for a in world.agents():
        view = LocalView(a, 100, 0, 1, world.observe(a, 100).data)
        qs = FORAGING_SB.labelled_questions(world, view, 100)
        kinds = [q.kind for q in qs]
        assert kinds.count("judgement") <= 2 and kinds.count("move") == 1
        move = next(q for q in qs if q.kind == "move")
        assert move.label in ACTIONS and move.label == FORAGING_SB.oracle_action(world, a, 100)
        assert all(isinstance(q.label, bool) for q in qs if q.kind == "judgement")
    # after the patch moved, the stale food memory is labelled "gone"
    stale = [q for a in world.agents() for q in FORAGING_SB.labelled_questions(
        world, LocalView(a, 100, 0, 1, world.observe(a, 100).data), 100) if q.qid == "food_still_there"]
    assert stale and not all(q.label for q in stale)


def test_oracle_walks_the_true_shortest_path():
    world = lone(100)
    place(world, a0=world.positions["0"])
    world.positions["0"] = next_to(world, [(4, 5)])[0]
    for tick in range(1, 80):
        world.apply("0", Intent(FORAGING_SB.oracle_action(world, "0", tick)), tick)
    assert world.deliveries >= 2  # alone on the map the oracle shuttles food to the nest


def test_oracle_actions_lists_every_shortest_path_first_step():
    world = lone(100)
    world.walls = set()
    world.food = {(8, 8)}
    world.nest = {(0, 0)}
    world.carrying["0"] = False
    world.positions["0"] = (4, 5)  # food at (8, 8), open map: east and south both shorten the way
    acts = FORAGING_SB.oracle_actions(world, "0", 1)
    assert set(acts) == {"east", "south"} and acts[0] == FORAGING_SB.oracle_action(world, "0", 1)
    world.positions["0"] = (8, 3)  # straight line: one direction only
    assert FORAGING_SB.oracle_actions(world, "0", 1) == ("south",)
    world.positions["0"] = (8, 7)  # next to the food
    assert FORAGING_SB.oracle_actions(world, "0", 1) == ("pick_up",)
    world.carrying["0"] = True
    world.positions["0"] = (1, 0)
    assert FORAGING_SB.oracle_actions(world, "0", 1) == ("drop",)
    world.positions["0"] = (3, 1)  # carrying, nest at (0, 0): west and north both shorten it
    assert set(FORAGING_SB.oracle_actions(world, "0", 1)) == {"west", "north"}
    world.positions["0"] = (0, 0)  # standing on the nest cell, off the walkable map: still answers
    assert FORAGING_SB.oracle_actions(world, "0", 1)
    world.positions["0"] = (3, 1)
    view = LocalView("0", 1, 0, 1, world.observe("0", 1).data)
    move = next(q for q in FORAGING_SB.labelled_questions(world, view, 1) if q.kind == "move")
    assert move.accept == FORAGING_SB.oracle_actions(world, "0", 1) and move.label == move.accept[0]


# --- validity check ----------------------------------------------------------


@pytest.fixture(scope="module")
def validity():
    return validity_check(DEV_SEEDS)


def test_validity_check_passes_for_both_variants_on_dev_seeds(validity):
    assert validity["seeds"] == list(range(100, 110)) and validity["pass"]
    for variant, row in validity["variants"].items():
        assert row["score_Sprime_base"] >= 0.9 * row["score_S_base"], variant
        assert row["score_S_variant"] <= 0.5 * row["score_Sprime_variant"], variant


def test_committed_validity_file_matches_a_fresh_run(validity):
    assert json.loads(RESULT.read_text()) == validity


def test_eval_seeds_are_not_used_for_tuning():
    assert not set(DEV_SEEDS) & set(range(1, 6))


# --- kernel isolation --------------------------------------------------------


def test_kernel_never_imports_a_world():
    offenders = [str(p.relative_to(ROOT)) for p in (ROOT / "antelligence/kernel").rglob("*.py")
                 if re.search(r"^\s*(from|import)\s+antelligence\.worlds", p.read_text(), re.M)]
    assert offenders == []


def test_width_constant_matches_published_map():
    assert WIDTH == 10 and asyncio  # 10x10 map, 10 agents, 100 rounds


def test_describe_declares_episode_length():
    from antelligence.worlds.foraging_sb import FORAGING_SB
    from antelligence.worlds.foraging_sb.world import STEPS
    assert FORAGING_SB.describe()["max_ticks"] == STEPS
