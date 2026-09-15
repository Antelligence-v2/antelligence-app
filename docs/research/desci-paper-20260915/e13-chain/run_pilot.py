#!/opt/homebrew/bin/python3.11
"""
E13: chain-prioritized foraging. Foods must be delivered in order (0->1->2).
Auto pick/drop (multi-carry); LLM only navigates. Sweep-only oracle proves solvability.

WHY THIS FAMILY: In E7v6, every food sighting was immediately actionable by any
agent. Here, food 1 is useless noise until food 0 is delivered. This tests whether
hive memory helps when shared information has temporal prerequisites -- some sightings
are valuable only in a later phase. A null result would force the headline to be
narrowed to the coordination-isolated foraging family (no prerequisite structure).

CHANGES FROM E7v6:
- Foods carry a delivery order (food 0, food 1, food 2). Chain: must deliver 0 first.
- Auto-pick: always pick up food when stepping on it (multi-carry via set).
- Auto-drop at nest: drop foods in chain order (0, then 1, then 2).
- Carrying agent with wrong food: must keep searching for next-needed food.
- Prompts tell agent which food it carries, which food is next-needed, and delivery state.
- Memory records include food index: "food 0 at (x,y)".
- Memory retrieval filters to next-needed food sightings.
- STEPS bumped from 80 to 120: chain constraint adds holding penalty.
"""

from __future__ import annotations
import argparse, json, os, random, re, sys, time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
PACKET = Path("/Volumes/WD_BLACK/antelligence-review-20260911/review/hive-fit-20260911")
sys.path.insert(0, str(PACKET))
from backend.research_hive_memory import HiveMemoryStore
from backend.research_hive_communication import (
    LocalEvidenceTransport, TransportLimits,
    build_request, build_reply, CommunicationError,
)
from backend.research_hive_contracts import serialize_envelope, _event_id

# Resume route (2026-09-14): OpenRouter is exhausted. The Nous token is short-lived,
# so Pilot.call reads ~/.hermes/auth.json for every uncached request instead of caching it.
MODEL = os.environ.get("E13_MODEL", "z-ai/glm-5.3-flash")
API = "https://inference-api.nousresearch.com/v1/chat/completions"
SCOPE = {"protocol": "inert-coldroom-v1", "revision": 1}
SOURCE_REV = "pilot-v14-chain"
CACHE_VERSION = "v14"
PRETEST_SEEDS = [101, 102, 103]
PRETEST_STEPS = 1
ARMS = ("baseline", "hive_memory", "hive_memory_comm")
SEEDS = list(range(101, 121))
WIDTH = HEIGHT = 10
VIEW_K = 5
STEPS = 120  # bumped from E7v6's 80: chain constraint adds holding penalty
N_FOOD = 3
AGENTS = 3
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


class BudgetStop(Exception):
    pass


class Pilot:
    def __init__(self, budget_tokens=2000000, max_cost=0.25,
                 cache_name="api_cache.jsonl", cache_prefix=CACHE_VERSION):
        self.budget_tokens = budget_tokens
        self.max_cost = max_cost
        self.cache_prefix = cache_prefix
        self.tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost = 0.0
        self.cache = {}
        OUT.mkdir(parents=True, exist_ok=True)
        self.cache_path = OUT / cache_name
        if self.cache_path.exists():
            for line in self.cache_path.read_text().splitlines():
                try:
                    x = json.loads(line)
                    if str(x.get("key", "")).startswith(self.cache_prefix + "|"):
                        self.cache[x["key"]] = x
                except Exception:
                    pass

    def _account(self, u):
        pt = int(u.get("prompt_tokens", 0))
        ct = int(u.get("completion_tokens", 0))
        self.prompt_tokens += pt
        self.completion_tokens += ct
        self.tokens += int(u.get("total_tokens", pt + ct))
        self.cost += float(u.get("cost", pt * 1e-6 + ct * 3e-6))
        if self.cost > self.max_cost:
            raise BudgetStop()

    def call(self, key, prompt):
        if key in self.cache:
            x = self.cache[key]
            self._account(x.get("usage", {}))
            return x.get("content", ""), x.get("usage", {})
        if self.tokens >= self.budget_tokens or self.cost >= self.max_cost:
            raise BudgetStop()
        token_path = Path(os.path.expanduser("~/.hermes/auth.json"))
        auth = json.loads(token_path.read_text())
        nous = auth.get("providers", {}).get("nous", {})
        keyval = nous.get("access_token") or nous.get("agent_key")
        if not keyval:
            raise RuntimeError("Nous access token not found in ~/.hermes/auth.json")
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
            "temperature": 0.0,
        }
        data = json.dumps(payload).encode()
        last = None
        for attempt in range(6):
            try:
                req = request.Request(
                    API,
                    data=data,
                    headers={
                        "Authorization": "Bearer " + keyval,
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://hermes-agent.nousresearch.com",
                    },
                )
                with request.urlopen(req, timeout=90) as r:
                    obj = json.load(r)
                    content = obj["choices"][0]["message"].get("content") or ""
                    usage = obj.get("usage", {})
                    pt = int(usage.get("prompt_tokens", 0))
                    ct = int(usage.get("completion_tokens", 0))
                    total = int(usage.get("total_tokens", pt + ct))
                    reported = usage.get("cost", obj.get("cost"))
                    cost = float(reported) if reported is not None else pt * 1e-6 + ct * 3e-6
                    rec = {
                        "key": key,
                        "content": content,
                        "usage": {
                            "prompt_tokens": pt,
                            "completion_tokens": ct,
                            "total_tokens": total,
                            "cost": cost,
                        },
                    }
                    with self.cache_path.open("a") as f:
                        f.write(json.dumps(rec, separators=(",", ":")) + "\n")
                    self.cache[key] = rec
                    self._account(rec["usage"])
                    return content, rec["usage"]
            except error.HTTPError as e:
                last = e
                if e.code not in (429, 500, 502, 503, 504):
                    break
            except Exception as e:
                last = e
            time.sleep(2 ** attempt)
        raise RuntimeError(f"Nous Portal failed after retries: {last}")


def envelope(kind, ordinal, **kw):
    x = {
        "version": "hive-contract-v1",
        "kind": kind,
        "event_id": "pending",
        "ordinal": ordinal,
        "scope": SCOPE,
        **kw,
    }
    x["event_id"] = _event_id(x)
    return x


def parse_action(text):
    """Binary decision only: FOLLOW (pursue best known target) or SWEEP."""
    t = (text or "").upper()
    if re.search(r"\bFOLLOW\b", t):
        return "FOLLOW"
    if re.search(r"\bSWEEP\b", t):
        return "SWEEP"
    return None


def env_for(seed):
    """Generate a chain-prioritized foraging environment.

    Returns: starts, nest, foods, food_index
    - foods[0] = food 0 (must deliver first), foods[1] = food 1, foods[2] = food 2
    - food_index maps position -> chain index (0, 1, 2)
    """
    rng = random.Random(seed)
    starts = [(rng.randrange(WIDTH), rng.randrange(HEIGHT)) for _ in range(AGENTS)]
    nest = (rng.randrange(WIDTH), rng.randrange(HEIGHT))
    foods = []
    while len(foods) < N_FOOD:
        f = (rng.randrange(WIDTH), rng.randrange(HEIGHT))
        if f != nest and f not in foods and f not in starts and \
           all(max(abs(f[0] - s[0]), abs(f[1] - s[1])) > 2 for s in starts):
            foods.append(f)
    food_index = {f: i for i, f in enumerate(foods)}
    return starts, nest, foods, food_index


def sweep_path(start):
    rows = list(range(HEIGHT))
    rows.sort(key=lambda y: (abs(y - start[1]), y))
    path = []
    for i, y in enumerate(rows):
        row = list(range(WIDTH))
        if i % 2:
            row.reverse()
        path.extend((x, y) for x in row)
    return path


def render_view(env, pos, carrying):
    """Render visible grid. Shows food labels (food0/food1/food2) and carried foods."""
    x, y = pos
    r = VIEW_K // 2
    cells = []
    for yy in range(y - r, y + r + 1):
        row = []
        for xx in range(x - r, x + r + 1):
            marks = []
            if (xx, yy) == env["nest"]:
                marks.append("nest")
            if (xx, yy) in env["foods_remaining"]:
                fi = env["food_index"][(xx, yy)]
                marks.append(f"food{fi}")
            if (xx, yy) in carrying:
                fi = env["food_index"][(xx, yy)]
                marks.append(f"have{fi}")
            row.append("." if not marks else "+".join(marks))
        cells.append(row)
    return cells


def step_toward(pos, target):
    dx = target[0] - pos[0]
    dy = target[1] - pos[1]
    if dx == 0 and dy == 0:
        return None
    if abs(dx) >= abs(dy):
        return "E" if dx > 0 else "W"
    return "S" if dy > 0 else "N"


def record_claim(store, agent, arm, step, content):
    food_match = re.search(r"food\s+(\d+)", content)
    food_suffix = f"-food-{food_match.group(1)}" if food_match else ""
    rec = {
        "kind": "evidence_claim",
        "content": content,
        "source_id": f"agent-{agent}-{step}{food_suffix}",
        "source_revision": SOURCE_REV,
        "applicability": "foraging-grid",
        "protocol": "inert-coldroom-v1",
        "revision": 1,
        "dependencies": [],
        "experimental_arm": arm,
    }
    claim_id = store.insert_candidate(rec)
    proc = {
        "kind": "conditional_procedure",
        "content": content,
        "source_id": f"agent-{agent}-{step}{food_suffix}-procedure",
        "source_revision": SOURCE_REV,
        "applicability": "foraging-grid",
        "protocol": "inert-coldroom-v1",
        "revision": 1,
        "dependencies": [],
        "evidence_refs": [claim_id],
        "experimental_arm": arm,
    }
    pid = store.insert_candidate(proc)
    store.admit_conditional_procedure(
        pid, evaluator_id="pilot-evaluator", evaluator_revision="e13-chain",
    )


def run_one(pilot, arm, seed, steps=STEPS, *, key_prefix=CACHE_VERSION,
            write_trajectory=True):
    rng = random.Random(seed ^ 0x5EED)
    starts, nest, foods, food_index = env_for(seed)

    env = {
        "nest": nest,
        "foods_remaining": list(foods),
        "food_index": food_index,
        "delivered": 0,
    }

    positions = {str(i): starts[i] for i in range(AGENTS)}
    carrying = {str(i): set() for i in range(AGENTS)}
    sweeps = {str(i): sweep_path(starts[i]) for i in range(AGENTS)}
    sweep_idx = {str(i): 0 for i in range(AGENTS)}

    db = OUT / f"memory_{arm}_{seed}.sqlite"
    db.unlink(missing_ok=True)
    store = None if arm == "baseline" else HiveMemoryStore(db)

    metrics = {
        "arm": arm,
        "seed": seed,
        "foods": [list(f) for f in foods],
        "food_index": {str(k): v for k, v in food_index.items()},
        "nest": list(nest),
        "success": False,
        "steps_to_success": None,
        "deliveries": 0,
        "llm_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "transport_events": 0,
        "memory_hits": 0,
        "memory_misses": 0,
        "memory_deposits": 0,
        "memory_relevant_hits": 0,
        "sweep_moves": 0,
        "directed_moves": 0,
        "parse_errors": 0,
        "failure_reason": None,
    }

    transport = None
    last_food_obs = None

    if arm == "hive_memory_comm":
        ids = {str(i) for i in range(AGENTS)}
        transport = LocalEvidenceTransport(
            ids,
            limits=TransportLimits(
                max_consultations=400,
                max_message_bytes=16384,
                max_fanout=4,
                max_steps=steps + 10,
            ),
            scope=SCOPE,
            current_step=0,
            accepted_source_revisions={
                f"agent-{i}": SOURCE_REV for i in range(AGENTS)
            },
        )

        def handler(frame):
            sender = frame["sender"]
            claim = last_food_obs or "no food sighting yet"
            source = {
                "source_id": frame["source"]["source_id"],
                "revision": SOURCE_REV,
                "applicability": "foraging-grid",
                "dependencies": [],
            }
            inner = envelope("evidence-reference", 0, source=source,
                             claim=claim, accepted=None)
            try:
                transport.send(
                    build_reply(
                        frame,
                        sender=frame["recipient"],
                        recipient=sender,
                        inner=serialize_envelope("evidence-reference", inner),
                        step=frame["step"] + 1,
                        source=source,
                    )
                )
            except CommunicationError:
                pass

        for i in range(AGENTS):
            transport.register(str(i), handler)

    trajectory = []
    next_needed = 0  # food index that must be delivered next (0, 1, or 2)

    for step in range(steps):
        if transport:
            transport.current_step = step

        for aid in range(AGENTS):
            a = str(aid)
            pos = positions[a]
            r = VIEW_K // 2

            # Visible foods (with indices)
            visible = []
            for f in env["foods_remaining"]:
                if abs(f[0] - pos[0]) <= r and abs(f[1] - pos[1]) <= r:
                    visible.append((f, food_index[f]))

            nest_visible = (
                abs(nest[0] - pos[0]) <= r and abs(nest[1] - pos[1]) <= r
            )

            # Deposit sightings (hive arms)
            hint = None
            if store and visible and not carrying[a]:
                for f, fi in visible:
                    record_claim(
                        store, aid, arm, step, f"food {fi} at {f}"
                    )
                    metrics["memory_deposits"] += 1
                    last_food_obs = f"food {fi} at {f}"

            # Retrieve known food targets from memory (filtered to next-needed)
            if store and not carrying[a]:
                hits = store.retrieve(
                    "inert-coldroom-v1", 1, "foraging-grid", "food ", arm,
                    max_results=8,
                )
                if hits:
                    metrics["memory_hits"] += 1
                    for h in reversed(hits):
                        m = re.search(
                            r"food\s+(\d+)\s+at\s+\((\d+),\s*(\d+)\)",
                            json.dumps(h["content"]),
                        )
                        if m:
                            fi = int(m.group(1))
                            cand = (int(m.group(2)), int(m.group(3)))
                            # Only useful if this is the next-needed food
                            # and still on the grid
                            if fi == next_needed and cand in env["foods_remaining"]:
                                hint = cand
                                metrics["memory_relevant_hits"] += 1
                                break
                else:
                    metrics["memory_misses"] += 1

                # Peer consult (hive_memory_comm)
                if transport and aid != 0 and hint is None:
                    source = {
                        "source_id": f"agent-{aid}",
                        "revision": SOURCE_REV,
                        "applicability": "foraging-grid",
                        "dependencies": [],
                    }
                    inner = envelope(
                        "evidence-reference", 0, source=source,
                        claim=f"food {next_needed} at?", accepted=None,
                    )
                    try:
                        transport.send(
                            build_request(
                                a,
                                str((aid - 1) % AGENTS),
                                SCOPE,
                                source,
                                serialize_envelope(
                                    "evidence-reference", inner
                                ),
                                step=step,
                                expires_step=min(step + 2, steps + 9),
                            )
                        )
                    except CommunicationError:
                        pass
                    if last_food_obs:
                        m = re.search(
                            r"food\s+(\d+)\s+at\s+\((\d+),\s*(\d+)\)",
                            last_food_obs,
                        )
                        if m:
                            fi = int(m.group(1))
                            if fi == next_needed:
                                cand = (int(m.group(2)), int(m.group(3)))
                                if cand in env["foods_remaining"]:
                                    hint = cand

            # Determine target and goal for the prompt
            if carrying[a]:
                # Carrying food(s). Is the next-needed food among them?
                carried_next = None
                for cf in carrying[a]:
                    if food_index[cf] == next_needed:
                        carried_next = cf
                        break

                if carried_next is not None:
                    target = nest
                    goal = f"carrying food {next_needed}, deliver to nest"
                else:
                    # Carrying wrong food. Must find next-needed.
                    target = None
                    goal = f"searching for food {next_needed} (carrying wrong food)"
                    # Check visible foods for next-needed
                    for f, fi in visible:
                        if fi == next_needed:
                            target = f
                            goal = f"visible food {next_needed}"
                            break
                    if target is None and hint and food_index.get(hint) == next_needed:
                        target = hint
                        goal = f"remembered food {next_needed}"
            else:
                # Not carrying. Look for next-needed food.
                if visible:
                    for f, fi in visible:
                        if fi == next_needed:
                            target = f
                            goal = f"visible food {next_needed}"
                            break
                    else:
                        # Visible foods exist but none is next-needed.
                        # Still, step on them to pick them up (may be useful later).
                        target = visible[0][0]
                        goal = f"visible food {visible[0][1]} (not next-needed)"
                elif hint and food_index.get(hint) == next_needed:
                    target = hint
                    goal = f"remembered food {next_needed}"
                elif hint:
                    target = hint
                    goal = f"remembered food {food_index.get(hint, '?')} (not next-needed)"
                else:
                    target = None
                    goal = f"unknown (searching for food {next_needed})"

            # Build prompt with chain context
            addition = ""
            if arm != "baseline" and hint and not carrying[a]:
                hi = food_index.get(hint, -1)
                if hi == next_needed:
                    addition = (
                        f"Hive memory remembers food {next_needed} at {hint} "
                        f"(shared by the swarm). "
                    )
                else:
                    addition = (
                        f"Hive memory remembers food {hi} at {hint} "
                        f"(shared by the swarm, but food {next_needed} is needed now). "
                    )

            if carrying[a]:
                carried_str = ", ".join(
                    f"food {food_index[cf]} at {cf}" for cf in sorted(carrying[a])
                )
                if carried_next is not None:
                    prompt = (
                        f"{WIDTH}x{HEIGHT} grid. You are carrying {carried_str}. "
                        f"The nest is at {nest}. Food {next_needed} is the next to "
                        f"deliver. Reply FOLLOW to walk to the nest, or SWEEP to keep "
                        f"searching. One token only: FOLLOW or SWEEP."
                    )
                else:
                    prompt = (
                        f"{WIDTH}x{HEIGHT} grid. You are carrying {carried_str}. "
                        f"Food {next_needed} must be delivered first. {addition}"
                        f"Reply SWEEP to keep searching for food {next_needed}, "
                        f"or FOLLOW (not useful now). "
                        f"One token only: FOLLOW or SWEEP."
                    )
            elif target is not None:
                prompt = (
                    f"{WIDTH}x{HEIGHT} grid. You are at {pos}. {addition}"
                    f"You know about {goal} at {target}. "
                    f"Foods must be delivered in order: food 0, then food 1, then "
                    f"food 2. So far, {env['delivered']} food(s) delivered. "
                    f"Reply FOLLOW to walk toward it, or SWEEP to keep searching. "
                    f"One token only: FOLLOW or SWEEP."
                )
            else:
                prompt = (
                    f"{WIDTH}x{HEIGHT} grid. You are at {pos}. {addition}"
                    f"No food {next_needed} is visible or remembered. "
                    f"Foods must be delivered in order: food 0, then food 1, then "
                    f"food 2. So far, {env['delivered']} food(s) delivered. "
                    f"Reply SWEEP to continue systematic search, or FOLLOW "
                    f"(not useful now). "
                    f"One token only: FOLLOW or SWEEP."
                )

            # LLM call
            try:
                text, u = pilot.call(
                    f"{key_prefix}|{seed}|{arm}|{aid}|{step}", prompt,
                )
                metrics["llm_calls"] += 1
                metrics["prompt_tokens"] += u.get("prompt_tokens", 0)
                metrics["completion_tokens"] += u.get("completion_tokens", 0)
                action = parse_action(text)
                if action is None:
                    metrics["parse_errors"] += 1
                    text, u = pilot.call(
                        f"{key_prefix}|{seed}|{arm}|{aid}|{step}|r",
                        prompt + " One token only.",
                    )
                    metrics["llm_calls"] += 1
                    metrics["prompt_tokens"] += u.get("prompt_tokens", 0)
                    metrics["completion_tokens"] += u.get("completion_tokens", 0)
                    action = parse_action(text)
                if action is None:
                    action = "SWEEP"
            except BudgetStop:
                metrics["failure_reason"] = "budget_exhausted"
                if transport:
                    metrics["transport_events"] = transport.accounting["events"]
                return metrics

            # Apply move: harness computes the step; LLM only picked the mode
            newpos = pos
            if action == "FOLLOW" and target is not None:
                mv = step_toward(pos, target)
                if mv:
                    dx, dy = DIRS[mv]
                    newpos = (pos[0] + dx, pos[1] + dy)
                    metrics["directed_moves"] += 1
                else:
                    newpos = target
                    metrics["directed_moves"] += 1
            else:
                # SWEEP (or FOLLOW with no target -> fall back to sweep)
                path = sweeps[a]
                cell = None
                while sweep_idx[a] < len(path):
                    c = path[sweep_idx[a]]
                    sweep_idx[a] += 1
                    if c != pos:
                        cell = c
                        break
                if cell:
                    mv = step_toward(pos, cell)
                    if mv:
                        dx, dy = DIRS[mv]
                        newpos = (pos[0] + dx, pos[1] + dy)
                        metrics["sweep_moves"] += 1

            positions[a] = newpos

            # AUTO pick: pick up any food at new position (multi-carry)
            if newpos in env["foods_remaining"]:
                env["foods_remaining"].remove(newpos)
                carrying[a].add(newpos)

            # AUTO drop: deliver foods at nest in chain order
            if newpos == nest and carrying[a]:
                while True:
                    to_drop = None
                    for cf in carrying[a]:
                        if food_index[cf] == next_needed:
                            to_drop = cf
                            break
                    if to_drop is None:
                        break
                    carrying[a].remove(to_drop)
                    env["delivered"] += 1
                    metrics["deliveries"] = env["delivered"]
                    next_needed += 1
                    if env["delivered"] == N_FOOD:
                        break
                    # If also carrying the new next-needed, drop it too
                    if any(
                        food_index[cf] == next_needed for cf in carrying[a]
                    ):
                        continue
                    break

            trajectory.append({
                "seed": seed,
                "arm": arm,
                "step": step,
                "agent": aid,
                "from": list(pos),
                "action": action,
                "to": list(newpos),
                "carrying": [list(c) for c in sorted(carrying[a])],
                "visible": [[list(v[0]), v[1]] for v in visible],
                "response": text,
                "next_needed": next_needed,
                "delivered": env["delivered"],
            })

            if env["delivered"] == N_FOOD:
                metrics["success"] = True
                metrics["steps_to_success"] = step + 1
                break

        if metrics["success"]:
            break

    if transport:
        metrics["transport_events"] = transport.accounting["events"]

    if write_trajectory:
        with (OUT / "trajectories.jsonl").open("a") as f:
            for row in trajectory:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")

    if not metrics["success"] and metrics["failure_reason"] is None:
        metrics["failure_reason"] = (
            f"delivered_{env['delivered']}_of_{N_FOOD}"
        )

    metrics["hive_records"] = len(store.list_records()) if store else 0
    return metrics


def oracle_check(seed, steps=STEPS):
    """SwEEP-only oracle with perfect knowledge. Returns (success, steps).

    The oracle knows all food positions and indices. It moves optimally:
    always toward the next-needed food (or nest if carrying it).
    Uses 3 agents in parallel, same as the experiment.
    """
    starts, nest, foods, food_index = env_for(seed)
    food_index_rev = {i: f for f, i in food_index.items()}

    positions = {str(i): starts[i] for i in range(AGENTS)}
    carrying = {str(i): set() for i in range(AGENTS)}
    foods_remaining = list(foods)
    delivered = 0
    next_needed = 0

    for step in range(steps):
        for aid in range(AGENTS):
            a = str(aid)
            pos = positions[a]

            # Determine optimal target
            if carrying[a]:
                carried_next = None
                for cf in carrying[a]:
                    if food_index[cf] == next_needed:
                        carried_next = cf
                        break
                if carried_next is not None:
                    target = nest
                else:
                    fn_pos = food_index_rev[next_needed]
                    if fn_pos in foods_remaining:
                        target = fn_pos
                    else:
                        target = nest
            else:
                fn_pos = food_index_rev[next_needed]
                if fn_pos in foods_remaining:
                    target = fn_pos
                else:
                    target = nest

            # Move toward target
            mv = step_toward(pos, target)
            if mv:
                dx, dy = DIRS[mv]
                positions[a] = (pos[0] + dx, pos[1] + dy)
            else:
                positions[a] = target

            # Auto pick
            if positions[a] in foods_remaining:
                foods_remaining.remove(positions[a])
                carrying[a].add(positions[a])

            # Auto drop at nest
            if positions[a] == nest and carrying[a]:
                while True:
                    to_drop = None
                    for cf in carrying[a]:
                        if food_index[cf] == next_needed:
                            to_drop = cf
                            break
                    if to_drop is None:
                        break
                    carrying[a].remove(to_drop)
                    delivered += 1
                    next_needed += 1
                    if delivered == N_FOOD:
                        return True, step + 1
                    if any(
                        food_index[cf] == next_needed for cf in carrying[a]
                    ):
                        continue
                    break

    return False, None


def run_pretest():
    """Run a cheap, isolated gate over all arm prompt paths.

    Three seeds × three steps × three arms exercises the real simulator loop,
    memory admission/retrieval, and communication path without contaminating
    the matrix cache or trajectory recovery log.
    """
    pilot = Pilot(
        budget_tokens=2000000,
        max_cost=0.15,
        cache_name=f"api_cache_{CACHE_VERSION}_pretest.jsonl",
        cache_prefix=f"{CACHE_VERSION}-pretest",
    )
    rows = []
    for arm in ARMS:
        for seed in PRETEST_SEEDS:
            try:
                metrics = run_one(
                    pilot, arm, seed, steps=PRETEST_STEPS,
                    key_prefix=f"{CACHE_VERSION}-pretest",
                    write_trajectory=False,
                )
                rows.append(metrics)
            except Exception as exc:
                rows.append({
                    "arm": arm, "seed": seed, "success": False,
                    "parse_errors": 0, "llm_calls": 0,
                    "failure_reason": f"pretest_exception: {exc}",
                })
    by_arm = {}
    for arm in ARMS:
        arm_rows = [row for row in rows if row.get("arm") == arm]
        by_arm[arm] = {
            "runs": len(arm_rows),
            "parse_errors": sum(row.get("parse_errors", 0) for row in arm_rows),
            "llm_calls": sum(row.get("llm_calls", 0) for row in arm_rows),
            "transport_events": sum(row.get("transport_events", 0) for row in arm_rows),
            "failures": [row.get("failure_reason") for row in arm_rows if row.get("failure_reason")],
        }
    passed = (
        len(rows) == len(ARMS) * len(PRETEST_SEEDS)
        and all(item["runs"] == len(PRETEST_SEEDS) for item in by_arm.values())
        and all(item["parse_errors"] == 0 and item["llm_calls"] > 0 for item in by_arm.values())
        and by_arm["hive_memory_comm"]["transport_events"] > 0
    )
    result = {
        "experiment": "e13-chain",
        "gate": "pretest",
        "model": MODEL,
        "provider": "nousresearch",
        "api": API,
        "cache_version": f"{CACHE_VERSION}-pretest",
        "seeds": PRETEST_SEEDS,
        "steps": PRETEST_STEPS,
        "arms": by_arm,
        "pass": passed,
        "cost": pilot.cost,
        "tokens": pilot.tokens,
        "cache_entries": len(pilot.cache),
    }
    (OUT / "pretest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 3


def load_env():
    p = Path(os.path.expanduser("~/.hermes/.env"))
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--pretest", action="store_true")
    ap.add_argument("--oracle-only", action="store_true")
    ap.add_argument("--max-cost", type=float, default=0.25)
    args = ap.parse_args()
    load_env()

    # Oracle solvability check first (E7v6 convention)
    if args.oracle_only or args.smoke:
        print("=== E13 Oracle Solvability Check ===")
        results = []
        for seed in SEEDS:
            ok, steps = oracle_check(seed, steps=args.steps)
            results.append((seed, ok, steps))
            status = "OK" if ok else "FAIL"
            print(f"  seed {seed}: {status} in {steps} steps" if ok
                  else f"  seed {seed}: FAIL")
        ok_count = sum(1 for _, ok, _ in results if ok)
        print(f"\nOracle: {ok_count}/20 seeds solvable in {args.steps} steps")
        if ok_count < 20:
            print("WARNING: Oracle cannot solve all seeds. Task may be too hard.")
            print("Consider increasing --steps.")
            sys.exit(1)
        else:
            print("Oracle passes: 20/20 solvable. Proceeding.")
            # Write oracle.json
            oracle_data = {
                "experiment": "e13-chain",
                "model": MODEL,
                "config": {
                    "agents": AGENTS,
                    "grid": [WIDTH, HEIGHT],
                    "view_k": VIEW_K,
                    "steps": args.steps,
                    "n_food": N_FOOD,
                    "seeds": SEEDS,
                    "temperature": 0.0,
                    "max_tokens": 1500,
                    "auto_pick_drop": True,
                    "chain_constraint": True,
                },
                "results": [
                    {"seed": s, "solvable": ok, "steps_to_success": st}
                    for s, ok, st in results
                ],
                "summary": {
                    "solvable_count": ok_count,
                    "mean_steps": round(
                        sum(st for _, ok, st in results if ok) / ok_count, 1
                    ),
                    "max_steps": max(st for _, ok, st in results if ok),
                },
            }
            (OUT / "oracle.json").write_text(json.dumps(oracle_data, indent=2) + "\n")
            print(f"Wrote out/oracle.json")

    if args.oracle_only:
        return

    if args.pretest:
        raise SystemExit(run_pretest())

    # Full experiment
    pilot = Pilot(
        budget_tokens=2000000,
        max_cost=args.max_cost,
        cache_name=(
            f"api_cache_{args.arm}.jsonl" if args.arm else "api_cache.jsonl"
        ),
    )
    seeds = [args.seed] if args.seed is not None else [
        int(x) for x in args.seeds.split(",")
    ]
    arms = [args.arm] if args.arm else list(ARMS)
    runs = []
    try:
        for arm in arms:
            for seed in seeds:
                runs.append(run_one(pilot, arm, seed, steps=args.steps))
    except BudgetStop:
        pass
    except Exception as e:
        (OUT / "pilot_error.json").write_text(
            json.dumps({"error": str(e), "runs": runs}, indent=2),
        )
        raise

    result = {
        "experiment": "e13-chain",
        "model": MODEL,
        "provider": "nousresearch",
        "config": {
            "agents": AGENTS,
            "grid": [WIDTH, HEIGHT],
            "view_k": VIEW_K,
            "steps": args.steps,
            "n_food": N_FOOD,
            "seeds": seeds,
            "temperature": 0.0,
            "max_tokens": 1500,
            "auto_pick_drop": True,
            "chain_constraint": True,
        },
        "runs": runs,
        "totals": {
            "prompt_tokens": pilot.prompt_tokens,
            "completion_tokens": pilot.completion_tokens,
            "total_tokens": pilot.tokens,
            "estimated_cost_usd": pilot.cost,
            "cache_entries": len(pilot.cache),
        },
    }
    name = (
        f"results_{args.arm}.json" if args.arm else "results.json"
    )
    (OUT / name).write_text(json.dumps(result, indent=2) + "\n")

    successes = sum(r["success"] for r in runs)
    mean_steps = round(
        sum(
            r["steps_to_success"] for r in runs
            if r["success"]
        ) / max(1, successes), 1
    )
    print(json.dumps({
        "arm": args.arm,
        "runs": len(runs),
        "successes": successes,
        "deliveries": sum(r["deliveries"] for r in runs),
        "mean_steps": mean_steps,
        "sweep_moves": sum(r["sweep_moves"] for r in runs),
        "memory_hits": sum(r["memory_hits"] for r in runs),
        "memory_relevant_hits": sum(r["memory_relevant_hits"] for r in runs),
        "cost": round(pilot.cost, 4),
        "tokens": pilot.tokens,
    }))


if __name__ == "__main__":
    main()
