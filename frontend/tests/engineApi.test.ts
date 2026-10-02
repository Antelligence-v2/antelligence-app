import assert from "node:assert/strict";
import test from "node:test";
import { z } from "zod";

import {
  ApiError, RunSchema, WorldSchema, fetchAllEvents, toApiError, type EventPage,
} from "../src/api/engine.ts";
import { event, run, world } from "./fixtures/engine.ts";

test("world catalog parses, and optional catalog fields may be absent", () => {
  const parsed = WorldSchema.parse(world);
  assert.equal(parsed.primary_metric, "sweep_moves");
  assert.equal(parsed.metric_label, undefined);
  assert.deepEqual(WorldSchema.parse({ ...world, metric_label: "moves" }).metric_label, "moves");
});

test("run parses and keeps unknown fields (passthrough)", () => {
  const parsed = RunSchema.parse({ ...run, future_field: 1 });
  assert.equal(parsed.bundle.trust.trust_tier, "local_replay");
  assert.equal((parsed as Record<string, unknown>).future_field, 1);
});

test("run missing a required field is rejected (drift fails loudly)", () => {
  const { trace_hash: _drop, ...broken } = run;
  assert.throws(() => RunSchema.parse(broken), z.ZodError);
});

test("toApiError reads FastAPI string and validation details", () => {
  const notFound = toApiError({ response: { status: 404, data: { detail: "run not found" } } });
  assert.equal(notFound.message, "run not found");
  assert.equal(notFound.status, 404);
  const invalid = toApiError({ response: { status: 422, data: { detail: [{ msg: "field required" }, { msg: "bad case" }] } } });
  assert.equal(invalid.message, "field required; bad case");
});

test("toApiError explains transport failures and local-only rejections", () => {
  assert.match(toApiError({ message: "Network Error" }).message, /Can't reach the engine/);
  assert.equal(toApiError({ response: { status: 403, data: {} } }).status, 403);
  assert.match(toApiError({ response: { status: 403, data: {} } }).message, /local requests/);
  const zod = toApiError(RunSchema.safeParse({}).error);
  assert.ok(zod instanceof ApiError);
  assert.match(zod.message, /Unexpected response/);
});

test("fetchAllEvents walks pages until total and preserves order", async () => {
  const all = Array.from({ length: 25 }, (_, i) => event(i));
  const calls: Array<[number, number]> = [];
  const page = async (offset: number, limit: number): Promise<EventPage> => {
    calls.push([offset, limit]);
    return { run_id: "r", total: all.length, offset, trace_hash: "t", events: all.slice(offset, offset + limit) };
  };
  const result = await fetchAllEvents(page, 10);
  assert.deepEqual(result.events.map((e) => e.seq), all.map((e) => e.seq));
  assert.deepEqual(calls, [[0, 10], [10, 10], [20, 10]]);
});

test("fetchAllEvents stops on an empty page instead of looping", async () => {
  const page = async (offset: number): Promise<EventPage> =>
    ({ run_id: "r", total: 50, offset, trace_hash: "t", events: offset === 0 ? [event(0)] : [] });
  const result = await fetchAllEvents(page, 10);
  assert.equal(result.events.length, 1);
});
