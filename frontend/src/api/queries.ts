/** React Query bindings for the engine API: one place for keys, caching and invalidation. */
import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { engine } from "./client";
import type { ApiError, ExperimentBody, RunRequest } from "./engine";

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
