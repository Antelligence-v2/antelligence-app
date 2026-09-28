/** Network layer for the engine API: one axios instance, validated responses. */
import axios from "axios";
import type { z } from "zod";
import { API_BASE_URL } from "@/lib/runtime";
import {
  EventPageSchema,
  HealthSchema,
  ExperimentListItemSchema,
  ExperimentSchema,
  ReplaySchema,
  RunSchema,
  WorldSchema,
  fetchAllEvents,
  toApiError,
  type ExperimentBody,
  type RunRequest,
} from "./engine";

const http = axios.create({ baseURL: `${API_BASE_URL}/engine`, timeout: 120_000 });

async function call<S extends z.ZodTypeAny>(schema: S, request: Promise<{ data: unknown }>): Promise<z.infer<S>> {
  try {
    const { data } = await request;
    return schema.parse(data);
  } catch (error) {
    throw toApiError(error);
  }
}

export const engine = {
  health: (signal?: AbortSignal) => call(HealthSchema, http.get("/health", { signal })),
  worlds: (signal?: AbortSignal) => call(WorldSchema.array(), http.get("/worlds", { signal })),
  run: (runId: string, signal?: AbortSignal) => call(RunSchema, http.get(`/runs/${encodeURIComponent(runId)}`, { signal })),
  createRun: (body: RunRequest) => call(RunSchema.omit({ outbox: true }), http.post("/runs", body)),
  events: (runId: string, signal?: AbortSignal) =>
    fetchAllEvents((offset, limit) =>
      call(EventPageSchema, http.get(`/runs/${encodeURIComponent(runId)}/events`, { params: { offset, limit }, signal }))),
  verify: (runId: string) => call(ReplaySchema, http.post(`/runs/${encodeURIComponent(runId)}/verify`)),
  experiments: (signal?: AbortSignal) => call(ExperimentListItemSchema.array(), http.get("/experiments", { signal })),
  experiment: (id: string, signal?: AbortSignal) => call(ExperimentSchema, http.get(`/experiments/${encodeURIComponent(id)}`, { signal })),
  createExperiment: (body: ExperimentBody) => call(ExperimentSchema, http.post("/experiments", body, { timeout: 600_000 })),
};
