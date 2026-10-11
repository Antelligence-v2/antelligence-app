# graph_coloring

A deterministic, seeded port of the **coloring** task from
[AgentsNet](https://github.com/floriangroetschla/AgentsNet) (Grötschla et al., MIT licence,
paper: <https://arxiv.org/abs/2507.08616>) for the v4 pilot. Eight agents sit on a graph and must each pick a
colour so that neighbours differ; they can only talk to their neighbours. The AgentsNet source was read, never
run or imported.

Score: the fraction of properly coloured edges, checked exactly. An agent with no colour leaves its edges improper.

## What is ported

- Graph families and parameters: connected Watts-Strogatz (k=4, p=0.4), Barabasi-Albert (m=2), Delaunay
  triangulation of uniform points. 8 nodes, palette of max-degree + 1 colours.
- Round rule: 4 synchronous rounds (AgentsNet's default for graphs of up to 16 nodes). What an agent announces in
  round r reaches its neighbours at the start of round r+1; round 1 hears nothing; the colour held after round 4
  is the final answer.

## Departures from AgentsNet

1. **Typed answers.** An action is `colour_<n>` (or `noop`) and is looked up exactly, never regex-parsed, so
   "Group 10" cannot read as "Group 1". Colours are shown to workers by name (red, blue, ...).
2. **No free-text messages.** The world owns the messages: taking a colour announces it (with an
   acknowledgement of the colour last heard from that neighbour); `noop` is silent.
3. **Own graph generators**, seeded, instead of networkx (not a declared dependency). Same families and
   parameters, different random streams, so the graphs are not AgentsNet's published ones. Graph family per
   seed is `seed % 3` -> ws, ba, dt.
4. **No chain of thought, no prompts, no LLM agents inside the world**; the sensing layer writes a short state.
5. **Palette names and score**: AgentsNet scores invalid answers as 0 for the whole run; here an uncoloured agent
   only makes its own edges improper.
6. **Variants** (below) are not in AgentsNet.

## Conditions

| id | what breaks | S' |
|----|-------------|----|
| base | nothing | - |
| v1 "lost messages" | each message dropped with p=0.3 (seeded) | re-announces until acknowledged; colours itself in the last round from what it heard |
| v2 "one liar" | agent 1 announces a random colour to each neighbour every round; only honest agents' edges are scored | knows the liar and ignores it |

S is a patient name-priority greedy: colour yourself once, after every lower-id neighbour has reported a
settled colour; never guess. Because of that wait it is not perfect on base (some chains are longer than 4
rounds), and the check in `variants.py` records how much.

### v2 differs from the first draft

As briefed, a liar that sends random colours only when it acts cannot hurt an honest edge (a lie about an edge
that is not scored changes nothing), and a recolour-on-clash S stayed above 0.9 of S'. The variant was
changed within its definition: the liar chatters every round, sits at a fixed id (1), and S waits for neighbours'
reports to settle. Dev seeds 100-109 were used to choose it; evaluation seeds are untouched.

## Run

`validity_check` (no model calls): `uv run python -m antelligence.worlds.graph_coloring.variants` writes
`docs/research/v4-pilot-20261011/validity-graph_coloring.json`. Tests: `tests/engine/test_graph_coloring.py`.
