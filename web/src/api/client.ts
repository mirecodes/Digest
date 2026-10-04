import type { PaperEntry, ViewerData } from "../types";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const listPapers = () => getJson<PaperEntry[]>("/api/papers");
export const loadViewer = (id: string) => getJson<ViewerData>(`/api/papers/${id}/viewer.json`);
export async function startAnnotate(id: string): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`/api/papers/${id}/annotate`, { method: "POST" });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error ?? res.statusText);
  return res.json();
}
export const jobEventsUrl = (jobId: string) => `/api/jobs/${jobId}/events`;
export const cropUrl = (id: string, page: number, bbox: number[]) =>
  `/api/papers/${id}/crop?page=${page}&bbox=${bbox.map((v) => v.toFixed(2)).join(",")}`;
