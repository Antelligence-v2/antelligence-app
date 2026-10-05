import assert from "node:assert/strict";
import test from "node:test";

import { agentLanes, describeEvent, filterEvents, findOrigin, inlineParams, naturalCompare } from "../src/features/runs/describe.ts";
import type { EngineEvent } from "../src/api/engine.ts";

const ev = (seq: number, tick: number, type: string, agent: string | null, data: Record<string, unknown> = {}): EngineEvent =>
  ({ seq, tick, type, agent_id: agent, data, prev_hash: "p", hash: "h" });

test("describeEvent summarizes decisions, outcomes, signals, memory and blocks", () => {
  assert.deepEqual(describeEvent(ev(1, 1, "decided", "bot-1", { action: "target", params: { cell_id: 72 }, rationale: "nearest sensed cell", cites: [] })),
    { title: "Decided target", detail: "cell_id 72 · “nearest sensed cell”", tone: "primary" });
  assert.equal(describeEvent(ev(2, 1, "outcome", "bot-1", { accepted: true, action: "advance", effects: { pos: [79.005, 243.1] } })).detail, "pos [79.0, 243.1]");
  assert.equal(describeEvent(ev(3, 1, "outcome", "bot-1", { accepted: false, action: "deliver", reason: "no payload" })).tone, "warning");
  assert.equal(describeEvent(ev(4, 1, "signal_deposited", "bot-1", { kind: "found", payload: { cells: 2 }, ttl: 20 })).detail, "cells 2 · ttl 20");
  assert.equal(describeEvent(ev(5, 3, "memory_changed", "1", { subject: "food:0", from: null, to: "candidate", reason: "proposed_by:1" })).detail, "∅ → candidate · proposed_by:1");
  assert.deepEqual(describeEvent(ev(6, 4, "intent_blocked", "2", { action: "follow", reason: "evidence_changed_this_tick" })),
    { title: "Blocked follow", detail: "evidence changed this tick", tone: "danger" });
});

test("inlineParams handles empty and nested values", () => {
  assert.equal(inlineParams({}), "");
  assert.equal(inlineParams(null), "");
  assert.equal(inlineParams({ a: 1, b: "x" }), "a 1 · b x");
});

test("agentLanes keeps the strongest state per agent and tick, naturally sorted", () => {
  const lanes = agentLanes([
    ev(0, 1, "observed", "bot-10"), ev(1, 1, "outcome", "bot-10", { accepted: true }),
    ev(2, 1, "observed", "bot-2"), ev(3, 1, "intent_blocked", "bot-2"), ev(4, 1, "outcome", "bot-2", { accepted: true }),
    ev(5, 2, "signal_deposited", "bot-2"), ev(6, 2, "tick_ended", null),
  ]);
  assert.deepEqual(lanes.agents, ["bot-2", "bot-10"]);
  assert.equal(lanes.cells.get("bot-2")?.get(1), "blocked");
  assert.equal(lanes.cells.get("bot-2")?.get(2), "signaled");
  assert.equal(lanes.cells.get("bot-10")?.get(1), "acted");
  assert.ok(naturalCompare("bot-2", "bot-10") < 0);
});

test("filterEvents combines type, agent and tick", () => {
  const log = [ev(0, 1, "decided", "a"), ev(1, 1, "outcome", "a"), ev(2, 2, "decided", "b")];
  assert.deepEqual(filterEvents(log, { types: new Set(["decided"]), agent: null, tick: null }).map((e) => e.seq), [0, 2]);
  assert.deepEqual(filterEvents(log, { types: new Set(), agent: "a", tick: 1 }).map((e) => e.seq), [0, 1]);
});

test("findOrigin resolves signal and memory ids to the event that produced them", () => {
  const log = [ev(0, 1, "signal_deposited", "a", { id: "sig1" }), ev(1, 1, "memory_changed", "a", { record_id: "rec1" })];
  assert.equal(findOrigin(log, "sig1")?.seq, 0);
  assert.equal(findOrigin(log, "rec1")?.seq, 1);
  assert.equal(findOrigin(log, "nope"), undefined);
});
