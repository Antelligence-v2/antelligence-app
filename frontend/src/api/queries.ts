/** React Query bindings for the engine API: one place for keys, caching and invalidation. */
import { useCallback, useEffect, useRef, useState } from "react";
import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { engine } from "./client";
import {
  toApiError, type ApiError, type Experiment, type ExperimentBody, type ExperimentJob, type Frames, type RunJob, type RunRequest,
} from "./engine";

export const keys = {
  health: ["engine", "health"] as const,
  worlds: ["engine", "worlds"] as const,
  run: (id: string) => ["engine", "run", id] as const,
  events: (id: string) => ["engine", "events", id] as const,
  frames: (id: string) => ["engine", "frames", id] as const,
  experiments: ["engine", "experiments"] as const,
  experiment: (id: string) => ["engine", "experiment", id] as const,
};

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        // Client errors (bad id, local-only) won't fix themselves; retry only transport failures once.
        retry: (count, error) => count < 1 && (error as ApiError | undefined)?.status == null,
      },
    },
  });
}

export const useEngineHealth = () =>
  useQuery({ queryKey: keys.health, queryFn: ({ signal }) => engine.health(signal), staleTime: 15_000, refetchInterval: 30_000 });

// Catalog and finished runs are immutable for a session: cache them indefinitely.
export const useWorlds = () =>
  useQuery({ queryKey: keys.worlds, queryFn: ({ signal }) => engine.worlds(signal), staleTime: Infinity });

export const useRun = (id: string | undefined) =>
  useQuery({ queryKey: keys.run(id ?? ""), queryFn: ({ signal }) => engine.run(id!, signal), enabled: !!id, staleTime: Infinity });

export const useRunEvents = (id: string | undefined) =>
  useQuery({ queryKey: keys.events(id ?? ""), queryFn: ({ signal }) => engine.events(id!, signal), enabled: !!id, staleTime: Infinity });

export const useRunFrames = (id: string | undefined) =>
  useQuery({ queryKey: keys.frames(id ?? ""), queryFn: ({ signal }) => engine.frames(id!, signal), enabled: !!id, staleTime: Infinity });

export const useExperiments = () =>
  useQuery({ queryKey: keys.experiments, queryFn: ({ signal }) => engine.experiments(signal) });

export const useExperiment = (id: string | undefined) =>
  useQuery({ queryKey: keys.experiment(id ?? ""), queryFn: ({ signal }) => engine.experiment(id!, signal), enabled: !!id, staleTime: Infinity });

export function useCreateRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: RunRequest) => engine.createRun(body),
    onSuccess: (run) => client.setQueryData(keys.run(run.run_id), run),
  });
}

export function useVerifyRun() {
  return useMutation({ mutationFn: (runId: string) => engine.verify(runId) });
}

export function useCreateExperiment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ExperimentBody) => engine.createExperiment(body),
    onSuccess: (report) => {
      client.setQueryData(keys.experiment(report.experiment_id), report);
      void client.invalidateQueries({ queryKey: keys.experiments });
    },
  });
}

/**
 * Runs an experiment as a background job and polls its progress.
 * `start` resolves with the finished report (also seeded into the cache).
 */
export function useExperimentJob() {
  const client = useQueryClient();
  const [job, setJob] = useState<ExperimentJob | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  const start = useCallback(async (body: ExperimentBody): Promise<Experiment | null> => {
    setError(null);
    try {
      let current = await engine.startExperiment(body);
      setJob(current);
      while (current.status === "running") {
        await new Promise((resolve) => setTimeout(resolve, 350));
        if (!alive.current) return null;
        current = await engine.experimentJob(current.job_id);
        setJob(current);
      }
      if (current.status === "failed" || !current.experiment_id) throw new Error(current.error ?? "Experiment failed.");
      const report = await engine.experiment(current.experiment_id);
      client.setQueryData(keys.experiment(report.experiment_id), report);
      void client.invalidateQueries({ queryKey: keys.experiments });
      return report;
    } catch (e) {
      const err = toApiError(e);
      if (alive.current) setError(err);
      return null;
    } finally {
      if (alive.current) setJob((j) => (j && j.status === "running" ? null : j));
    }
  }, [client]);

  const running = job?.status === "running";
  return { start, job, running, error, reset: () => { setJob(null); setError(null); } };
}

/**
 * Runs one engine run as a background job: polls progress and streams the
 * frames recorded so far, so a long (LLM) run can be watched while it goes.
 * `start` resolves with the finished run id (null on failure or unmount).
 */
export function useRunJob() {
  const [job, setJob] = useState<RunJob | null>(null);
  const [live, setLive] = useState<Frames | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  // True from the click until the job ends, including the start request's round trip,
  // so a double-click or a second ⌘↵ can't launch another run.
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  const start = useCallback(async (body: RunRequest): Promise<string | null> => {
    if (inFlight.current) return null;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setLive(null);
    try {
      let current = await engine.startRun(body);
      setJob(current);
      let scene: Record<string, unknown> | null = null;
      const frames: Frames["frames"] = [];
      while (current.status === "queued" || current.status === "running") {
        await new Promise((resolve) => setTimeout(resolve, 400));
        if (!alive.current) return null;
        current = await withRetry(() => engine.runJob(current.job_id));
        if (current.status === "running") {
          const id = current.job_id;
          const page = await withRetry(() => engine.liveFrames(id, frames.length));
          if (page && page.frames.length) {
            scene = page.scene;
            frames.push(...page.frames);
            if (alive.current) setLive({ run_id: current.run_id, scene, frames: frames.slice() });
          }
        }
        if (alive.current) setJob(current);
      }
      if (current.status === "failed") throw new Error(current.error ?? "Run failed.");
      return current.run_id;
    } catch (e) {
      const err = toApiError(e);
      if (alive.current) setError(err);
      return null;
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(false);
    }
  }, []);

  const running = busy || job?.status === "queued" || job?.status === "running";
  return { start, job, live, running, error };
}

/** Retries a poll a few times with backoff, so one dropped request doesn't end the watch. */
async function withRetry<T>(call: () => Promise<T>, attempts = 4): Promise<T> {
  for (let i = 0; ; i++) {
    try {
      return await call();
    } catch (error) {
      const status = toApiError(error).status;
      // A 4xx is an answer, not a blip (404 on frames is handled by the caller as null).
      if (i + 1 >= attempts || (status !== null && status < 500)) throw error;
      await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** i));
    }
  }
}
