"""Golden 2D tumor runs: any change that alters a 2D trajectory must fail here.

The hashes were recorded from the 2D engine before 3D support existed (and
re-checked identical on PR #3 vs #4 by review). hive / hive_queen were re-pinned
after rebasing onto main, whose PR #2 review fix (L1: refuse observations made
before a subject's source changed) intentionally changes memory-arm runs; event
logs were verified identical to main's engine apart from the mean_living_cells
metric this branch adds. Update them only for an intentional, documented
change to 2D behavior.
"""

import pytest

from antelligence.experiments.registry import RunSpec, world

GOLDEN = [
    ("rule", 1, "a2b09c7104d11c433cf02c98b9e29d7be2dd768d04f8294383636f0cb3535228", "aa072029434acbc8a6cbf0d0ea6ccc538a74bd48aa976cccce0bd52187a17eda"),
    ("pheromone", 7, "7a74956d2b36b27b3e9dc1b246f1f9424015274d528a22e361f5f4c27d3c50eb", "33b62f70c10507e7ada228209723805a65db4865ce425f229aa84fb2b2d4c638"),
    ("hive", 1, "2035c827f517fb30a8d8ff138079d3118b6c1b9ad398891ab2b498b56498fefa", "44d109d66056508787b4d9127989cf4391e10f2f10280f8485077fdadc2f48af"),
    ("hive_queen", 7, "1a8a98d6dff6083fe207e4508a8277801cd05cb674c7910d6df87554f2c44170", "866115d2e3f662b5d4b700fb1cb69843de0096ba8257d982e60a0ef8d5e57025"),
    ("signals", 3, "05e0dde7c3449570d416c21e87f80366d69154c0aa0fbcbc1f746944f99bf15a", "d5486bdf6dde761d60ba755a93cef36e0004e5f805a1385b3b815b475425eaff"),
]


@pytest.mark.parametrize("arm,case,trace,config", GOLDEN, ids=[f"{a}-{c}" for a, c, _, _ in GOLDEN])
def test_2d_tumor_runs_match_golden_hashes(arm, case, trace, config):
    result = world("tumor").build(RunSpec("tumor", arm, case, {}), f"golden-{arm}-{case}").run()
    assert result.config_hash == config
    assert result.trace_hash == trace
