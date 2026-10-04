import { useEffect, useMemo, useState } from "react";
import { listPapers } from "../api/client";
import { navigate } from "../App";
import { t } from "../i18n";
import type { PaperEntry } from "../types";

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

export default function Library() {
  const [papers, setPapers] = useState<PaperEntry[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => {
    listPapers().then(setPapers, (e) => setError(String(e.message ?? e)));
  }, []);

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
            {list.map((p) => (
              <li key={p.id} data-paper-id={p.id}>
                <div className="info">
                  <div className="name">{p.name}</div>
                  <div className="meta"><span className="num">{p.num_pages} {t("pages")}</span><Chips p={p} /></div>
                </div>
                <button className="primary" disabled={p.status === "evicted"} onClick={() => navigate(`/r/${p.id}`)}>{t("open")}</button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
