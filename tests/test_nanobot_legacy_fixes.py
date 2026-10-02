"""Regression tests for two legacy nanobot bugs found while porting to the engine.

1. Payload deadlock: bots returned to reload only when payload < 2.0 but could
   target only when payload > 2.0; 20 - 6 x 3 = exactly 2.0, so every bot
   delivered one payload and then searched forever.
2. Boundary snap: an out-of-tumor searching bot was moved to the *opposite*
   edge of the tumor instead of the nearest one.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from nanobot_simulation import NanobotState, TumorNanobotModel  # noqa: E402
from runtime_factory import seed_rng  # noqa: E402


def model(**kwargs):
    seed_rng(1)
    return TumorNanobotModel(n_nanobots=10, agent_type="Rule-Based", with_queen=False, use_llm_queen=False,
                             seed=1, **kwargs)


def test_bot_with_exactly_two_micrograms_goes_to_reload_instead_of_searching_forever():
    m = model()
    bot = m.nanobots[0]
    bot.drug_payload = 2.0
    bot.state = NanobotState.SEARCHING
    bot.step()
    assert bot.state == NanobotState.RETURNING


def test_bots_deliver_more_than_one_payload_over_a_long_run():
    m = model()
    for _ in range(150):
        m.step()
    deliveries = sum(b.deliveries_made for b in m.nanobots)
    assert deliveries > 60, "legacy deadlock capped every run at 6 deliveries per bot"


def test_out_of_tumor_searching_bot_snaps_to_the_nearest_edge():
    m = model()
    bot = m.nanobots[0]
    center = np.array(m.geometry.center[:2])
    radius = m.geometry.tumor_radius
    bot.state = NanobotState.SEARCHING
    bot.drug_payload = bot.max_payload
    bot.position[:2] = center + np.array([radius + 40.0, 0.0])
    bot._enforce_tumor_boundary()
    assert bot.position[0] > center[0], "must land on the same (near) side of the tumor"
    assert abs(np.linalg.norm(bot.position[:2] - center) - (radius - 5.0)) < 1e-6


def test_returning_bot_reaches_its_vessel_instead_of_oscillating_around_it():
    """3. Vessel overshoot: 30 um steps against a 10 um arrival radius oscillated forever."""
    m = model()
    bot = m.nanobots[0]
    vessel = m.geometry.vessels[0]
    bot.state = NanobotState.RETURNING
    bot.drug_payload = 2.0
    bot.target_vessel = vessel
    bot.position[:2] = np.array(vessel.position[:2]) + np.array([16.0, 0.0])
    for _ in range(4):
        bot.step()
    assert bot.state in (NanobotState.RELOADING, NanobotState.SEARCHING)
