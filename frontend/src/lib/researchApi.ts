import axios from "axios";
import { API_BASE_URL } from "./runtime";
import type {
  ResearchCatalog,
  ResearchReport,
  ResearchRunRequest,
  ResearchRunsResponse,
} from "./researchTypes";

const endpoint = (path: string) => `${API_BASE_URL}/research${path}`;

export function apiErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (error?.response?.data?.message) return error.response.data.message;
  return error?.message || "The research backend request failed.";
}

export async function getResearchCatalog(signal?: AbortSignal): Promise<ResearchCatalog> {
  const response = await axios.get(endpoint("/catalog"), { signal });
  return response.data;
}

export async function listResearchRuns(signal?: AbortSignal): Promise<ResearchRunsResponse> {
  const response = await axios.get(endpoint("/runs?limit=50"), { signal });
  return response.data;
}

export async function getResearchRun(runId: string, signal?: AbortSignal): Promise<ResearchReport> {
  const response = await axios.get(endpoint(`/runs/${encodeURIComponent(runId)}`), { signal });
  return response.data;
}

export async function startResearchRun(request: ResearchRunRequest, signal?: AbortSignal): Promise<{ run_id: string; status: "running" }> {
  const response = await axios.post(endpoint("/runs"), request, { signal, timeout: 30000 });
  return response.data;
}

export async function cancelResearchRun(runId: string, signal?: AbortSignal): Promise<ResearchReport> {
  const response = await axios.post(endpoint(`/runs/${encodeURIComponent(runId)}/cancel`), undefined, { signal, timeout: 30000 });
  return response.data;
}
