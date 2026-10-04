import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { jobEventsUrl, listPapers, startAnnotate } from "../api/client";
import { navigate } from "../App";
import { t } from "../i18n";
import type { PaperEntry } from "../types";

type JobView = { status: string; lines: string[] };
const LOG_LINES = 200;

function Chips({ p }: { p: PaperEntry }) {
  return (
    <span className="chips">
      {p.digest_verify && <span className={`chip ${p.digest_verify === "PASS" ? "ok" : "bad"}`}>digest {p.digest_verify}</span>}
      <span className="chip">{t("translation")} {p.translation.done}/{p.translation.total}</span>
      <span className="chip">{t("highlights")} {p.highlights}</span>
      <span className="chip">{t("figure_notes")} {p.figure_notes.done}/{p.figure_notes.total}</span>
      {p.status === "evicted" && <span className="chip warn">{t("evicted")}</span>}
    </span>
  );
}

function JobLog({ job }: { job: JobView }) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [job.lines.length]);
  const label = { queued: t("job_queued"), running: t("job_running"), done: t("job_done"), failed: t("job_failed") }[job.status] ?? job.status;
  return (
    <div className="job" data-testid="job-log">
      <span className={`chip ${job.status === "done" ? "ok" : job.status === "failed" ? "bad" : ""}`} data-status={job.status}>{label}</span>
      <pre ref={ref}>{job.lines.join("\n") || "…"}</pre>
    </div>
  );
}

export default function Library() {
  const [papers, setPapers] = useState<PaperEntry[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [jobs, setJobs] = useState<Record<string, JobView>>({});
  const sources = useRef<EventSource[]>([]);

  const refresh = useCallback(() => listPapers().then(setPapers, (e) => setError(String(e.message ?? e))), []);
  useEffect(() => {
    refresh();
    return () => sources.current.forEach((s) => s.close());
  }, [refresh]);

  const preprocess = async (id: string) => {
    const update = (fn: (j: JobView) => JobView) => setJobs((all) => ({ ...all, [id]: fn(all[id] ?? { status: "queued", lines: [] }) }));
    try {
      const { job_id, status } = await startAnnotate(id);
      update(() => ({ status, lines: [] }));
      const es = new EventSource(jobEventsUrl(job_id));
      sources.current.push(es);
      es.addEventListener("log", (e) => update((j) => ({ ...j, lines: [...j.lines, JSON.parse(e.data).text].slice(-LOG_LINES) })));
      es.addEventListener("status", (e) => update((j) => ({ ...j, status: JSON.parse(e.data).status })));
      es.addEventListener("done", (e) => {
        update((j) => ({ ...j, status: JSON.parse(e.data).status }));
        es.close();
        refresh();
      });
    } catch (e) {
      update(() => ({ status: "failed", lines: [String((e as Error).message ?? e)] }));
    }
  };

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const map = new Map<string, PaperEntry[]>();
    for (const p of papers ?? []) {
      if (q && !p.folder_rel.toLowerCase().includes(q)) continue;
      const dir = p.folder_rel.includes("/") ? p.folder_rel.slice(0, p.folder_rel.lastIndexOf("/")) : "";
      map.set(dir, [...(map.get(dir) ?? []), p]);
    }
    return [...map.entries()];
  }, [papers, query]);

  return (
    <div className="library">
      <header className="library-head">
        <h1>{t("library")}</h1>
        <p>{t("library_sub")}</p>
        <input placeholder={t("search_papers")} value={query} onChange={(e) => setQuery(e.target.value)} aria-label={t("search_papers")} />
      </header>
      {error && <p className="error">{t("load_failed")}: {error}</p>}
      {papers === null && !error && <p className="empty-state">{t("loading")}</p>}
      {papers?.length === 0 && <p className="empty-state">{t("no_papers")}</p>}
      {groups.map(([dir, list]) => (
        <section key={dir}>
          {dir && <h2>{dir}</h2>}
          <ul className="paper-list">
            {list.map((p) => {
              const job = jobs[p.id];
              const busy = job && (job.status === "queued" || job.status === "running");
              return (
                <li key={p.id} data-paper-id={p.id}>
                  <div className="row">
                    <div className="info">
                      <div className="name">{p.name}</div>
                      <div className="meta"><span className="num">{p.num_pages} {t("pages")}</span><Chips p={p} /></div>
                    </div>
                    <button disabled={p.status === "evicted" || busy} onClick={() => preprocess(p.id)} title={t("preprocess_hint")}>
                      {t("preprocess")}
                    </button>
                    <button className="primary" disabled={p.status === "evicted"} onClick={() => navigate(`/r/${p.id}`)}>{t("open")}</button>
                  </div>
                  {job && <JobLog job={job} />}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
