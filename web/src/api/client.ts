import { t } from "../i18n";
import type { Action, AgentChoice, Config, JobInfo, PaperEntry, PrepareState, ViewerData } from "../types";

async function errorOf(res: Response): Promise<Error> {
  // 405: a server started before this route existed answers through the GET-only SPA catch-all
  if (res.status === 405) return new Error(t("server_outdated"));
  const body = await res.json().catch(() => ({}));
  return new Error(body.error ?? `${res.status} ${res.statusText}`);
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw await errorOf(res);
  return res.json();
}

export const listPapers = () => getJson<PaperEntry[]>("/api/papers");
export const loadViewer = (id: string) => getJson<ViewerData>(`/api/papers/${id}/viewer.json`);
export const getConfig = () => getJson<Config>("/api/config");
/** resume: keep the work an interrupted or failed run already finished. */
export async function startJob(id: string, action: Action, agent: AgentChoice, resume = false): Promise<{ job_id: string; status: string; action: Action }> {
  const res = await fetch(`/api/papers/${id}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...agent, resume }),
  });
  if (!res.ok) throw await errorOf(res);
  return res.json();
}
export const listJobs = () => getJson<JobInfo[]>("/api/jobs");
export const getPrepare = () => getJson<PrepareState>("/api/prepare");
export const cropUrl = (id: string, page: number, bbox: number[]) =>
  `/api/papers/${id}/crop?page=${page}&bbox=${bbox.map((v) => v.toFixed(2)).join(",")}`;
