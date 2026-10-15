/** Network layer for the engine API: one axios instance, validated responses. */
import type { AxiosInstance, AxiosRequestConfig } from "axios";
import type { z } from "zod";
import { API_BASE_URL } from "@/lib/runtime";
import {
  EventPageSchema,
  FramesSchema,
  HealthSchema,
  LiveFramesSchema,
  RunJobSchema,
  ExperimentJobSchema,
  ExperimentListItemSchema,
  ExperimentSchema,
  ReplaySchema,
  RunSchema,
  WorldSchema,
  fetchAllEvents,
  toApiError,
  ApiError,
  type ExperimentBody,
  type RunRequest,
} from "./engine";

// axios loads on the first request, which keeps it out of the entry chunk every page pays for.
let instance: Promise<AxiosInstance> | undefined;
const client = () => (instance ??= import("axios").then(({ default: axios }) => axios.create({ baseURL: `${API_BASE_URL}/engine`, timeout: 120_000 })));
const http = {
  get: (url: string, config?: AxiosRequestConfig) => client().then((c) => c.get(url, config)),
  post: (url: string, body?: unknown, config?: AxiosRequestConfig) => client().then((c) => c.post(url, body, config)),
};

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
  /** null when the run has no frames (non-spatial world or recorded before frames existed). */
  frames: async (runId: string, signal?: AbortSignal) => {
    try {
      return await call(FramesSchema, http.get(`/runs/${encodeURIComponent(runId)}/frames`, { signal }));
    } catch (error) {
      if (error instanceof ApiError && error.status === 404 && /no frames/.test(error.message)) return null;
      throw error;
    }
  },
  startRun: (body: RunRequest) => call(RunJobSchema, http.post("/runs/jobs", body)),
  runJob: (jobId: string) => call(RunJobSchema, http.get(`/runs/jobs/${encodeURIComponent(jobId)}`)),
  /** null while the run has not started (queued) or once it has finished. */
  liveFrames: async (jobId: string, since: number) => {
    try {
      return await call(LiveFramesSchema, http.get(`/runs/jobs/${encodeURIComponent(jobId)}/frames`, { params: { since } }));
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
  verify: (runId: string) => call(ReplaySchema, http.post(`/runs/${encodeURIComponent(runId)}/verify`)),
  experiments: (signal?: AbortSignal) => call(ExperimentListItemSchema.array(), http.get("/experiments", { signal })),
  experiment: (id: string, signal?: AbortSignal) => call(ExperimentSchema, http.get(`/experiments/${encodeURIComponent(id)}`, { signal })),
  startExperiment: (body: ExperimentBody) => call(ExperimentJobSchema, http.post("/experiments/jobs", body)),
  experimentJob: (jobId: string) => call(ExperimentJobSchema, http.get(`/experiments/jobs/${encodeURIComponent(jobId)}`)),
  createExperiment: (body: ExperimentBody) => call(ExperimentSchema, http.post("/experiments", body, { timeout: 600_000 })),
};
