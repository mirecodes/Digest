import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getConfig, jobEventsUrl, listPapers, startJob } from "../api/client";
import { navigate } from "../App";
import { t, type Key } from "../i18n";
import { CheckIcon, ChevronDownIcon } from "../reader/icons";
import type { Action, AgentChoice, AgentConfig, PaperEntry } from "../types";

type JobView = { status: string; action: Action; lines: string[] };
const LOG_LINES = 200;
const ACTIONS: { action: Action; label: Key; hint: Key }[] = [
  { action: "all", label: "action_all", hint: "action_all_hint" },
  { action: "digest", label: "action_digest", hint: "action_digest_hint" },
  { action: "translation", label: "action_translation", hint: "action_translation_hint" },
  { action: "highlights", label: "action_highlights", hint: "action_highlights_hint" },
  { action: "figures", label: "action_figures", hint: "action_figures_hint" },
];

const complete = (c: { done: number; total: number }) => c.total > 0 && c.done === c.total;

/** Whether an action is already done for the paper, and why it cannot run (null = it can). */
function actionState(p: PaperEntry, a: Action): { done: boolean; blocked: Key | null } {
  const digested = p.digest_verify === "PASS";
  const done = {
    digest: digested,
    translation: complete(p.translation),
    highlights: p.highlights > 0,
    figures: complete(p.figure_notes),
    all: digested && complete(p.translation) && p.highlights > 0 && complete(p.figure_notes),
  }[a];
  // every action stands alone (the job prepares the paper first); only a passed summary is not redone
  const blocked: Key | null = a === "digest" && digested ? "already_done" : null;
  return { done, blocked };
}

function Chips({ p }: { p: PaperEntry }) {
  if (p.status === "new") return <span className="chips"><span className="chip warn">{t("new_paper")}</span></span>;
  return (
    <span className="chips">
      {p.digest_verify && <span className={`chip ${p.digest_verify === "PASS" ? "ok" : "bad"}`}>{t("summary")} {p.digest_verify}</span>}
      <span className="chip">{t("translation")} {p.translation.done}/{p.translation.total}</span>
      <span className="chip">{t("highlights")} {p.highlights}</span>
      <span className="chip">{t("figure_notes")} {p.figure_notes.done}/{p.figure_notes.total}</span>
      {p.status === "evicted" && <span className="chip warn">{t("evicted")}</span>}
    </span>
  );
}

function ProcessMenu({ p, busy, onRun }: { p: PaperEntry; busy: boolean; onRun: (a: Action) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const escape = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  return (
    <div className="menu-wrap" ref={ref}>
      <button aria-haspopup="menu" aria-expanded={open} disabled={p.status === "evicted" || busy} onClick={() => setOpen((o) => !o)} title={t("process_hint")}>
        {t("process")} <ChevronDownIcon />
      </button>
      {open && (
        <div className="menu" role="menu">
          {ACTIONS.map(({ action, label, hint }) => {
            const { done, blocked } = actionState(p, action);
            return (
              <button
                key={action}
                role="menuitem"
                data-action={action}
                disabled={blocked !== null}
                title={t(blocked ?? hint)}
                onClick={() => {
                  setOpen(false);
                  onRun(action);
                }}
              >
                <span>{t(label)}</span>
                {done && <span className="done" aria-label={t("already_done")}><CheckIcon /></span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

const choiceKey = (backend: string) => `paper-viewer:agent:${backend}`;
function loadChoice(backend: string): AgentChoice {
  try {
    return { model: "", effort: "", ...JSON.parse(localStorage.getItem(choiceKey(backend)) ?? "{}") };
  } catch {
    return { model: "", effort: "" };
  }
}

/** Model and effort for the next jobs; empty = cfg.yaml. Remembered per backend in this browser. */
function AgentPicker({ cfg, choice, onChange }: { cfg: AgentConfig; choice: AgentChoice; onChange: (c: AgentChoice) => void }) {
  const set = (c: AgentChoice) => {
    onChange(c);
    try {
      localStorage.setItem(choiceKey(cfg.backend), JSON.stringify(c));
    } catch {
      /* private window: not remembered */
    }
  };
  const fallback = (v: string) => `${t("agent_default")} (${v || t("agent_cli_default")})`;
  return (
    <div className="agent-picker" title={t("agent_hint")}>
      <span className="chip">{cfg.backend}</span>
      <label>
        {t("agent_model")}
        <input
          list="agent-models"
          value={choice.model}
          placeholder={fallback(cfg.model)}
          onChange={(e) => set({ ...choice, model: e.target.value.trim() })}
        />
        <datalist id="agent-models">
          {cfg.models.map((m) => <option key={m} value={m} />)}
        </datalist>
      </label>
      {cfg.efforts.length > 0 && (
        <label>
          {t("agent_effort")}
          <select value={choice.effort} onChange={(e) => set({ ...choice, effort: e.target.value })}>
            <option value="">{fallback(cfg.effort)}</option>
            {cfg.efforts.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
      )}
    </div>
  );
}

function JobLog({ job }: { job: JobView }) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [job.lines.length]);
  const label = { queued: t("job_queued"), running: t("job_running"), done: t("job_done"), failed: t("job_failed") }[job.status] ?? job.status;
  const action = ACTIONS.find((a) => a.action === job.action);
  return (
    <div className="job" data-testid="job-log">
      <span className={`chip ${job.status === "done" ? "ok" : job.status === "failed" ? "bad" : ""}`} data-status={job.status}>
        {action ? `${t(action.label)} · ` : ""}{label}
      </span>
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
  const [agent, setAgent] = useState<AgentConfig | null>(null);
  const [choice, setChoice] = useState<AgentChoice>({ model: "", effort: "" });

  const refresh = useCallback(() => listPapers().then(setPapers, (e) => setError(String(e.message ?? e))), []);
  useEffect(() => {
    refresh();
    getConfig().then((c) => {
      if (!c.agent) return; // older server
      setAgent(c.agent);
      const saved = loadChoice(c.agent.backend);
      setChoice({ model: saved.model, effort: c.agent.efforts.includes(saved.effort) ? saved.effort : "" });
    }, () => {});
    return () => sources.current.forEach((s) => s.close());
  }, [refresh]);

  const run = async (id: string, action: Action) => {
    const update = (fn: (j: JobView) => JobView) =>
      setJobs((all) => ({ ...all, [id]: fn(all[id] ?? { status: "queued", action, lines: [] }) }));
    try {
      const job = await startJob(id, action, choice);
      update(() => ({ status: job.status, action: job.action, lines: [] }));
      const es = new EventSource(jobEventsUrl(job.job_id));
      sources.current.push(es);
      es.addEventListener("log", (e) => update((j) => ({ ...j, lines: [...j.lines, JSON.parse(e.data).text].slice(-LOG_LINES) })));
      es.addEventListener("status", (e) => update((j) => ({ ...j, status: JSON.parse(e.data).status })));
      es.addEventListener("done", (e) => {
        update((j) => ({ ...j, status: JSON.parse(e.data).status }));
        es.close();
        refresh();
      });
    } catch (e) {
      update(() => ({ status: "failed", action, lines: [String((e as Error).message ?? e)] }));
    }
  };

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const map = new Map<string, PaperEntry[]>();
    for (const p of papers ?? []) {
      if (q && !p.folder_rel.toLowerCase().includes(q) && !p.name.toLowerCase().includes(q)) continue;
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
        <input className="paper-search" placeholder={t("search_papers")} value={query} onChange={(e) => setQuery(e.target.value)} aria-label={t("search_papers")} />
        {agent && <AgentPicker cfg={agent} choice={choice} onChange={setChoice} />}
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
              const busy = !!job && (job.status === "queued" || job.status === "running");
              return (
                <li key={p.id} data-paper-id={p.id}>
                  <div className="row">
                    <div className="info">
                      <div className="name">{p.name}</div>
                      <div className="meta">
                        {p.status !== "new" && <span className="num">{p.num_pages} {t("pages")}</span>}
                        <Chips p={p} />
                      </div>
                    </div>
                    <ProcessMenu p={p} busy={busy} onRun={(a) => run(p.id, a)} />
                    <button className="primary" disabled={p.status !== "ok"} onClick={() => navigate(`/r/${p.id}`)}>{t("open")}</button>
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
