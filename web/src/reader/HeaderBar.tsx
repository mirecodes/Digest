import { useEffect, useMemo, useRef, useState } from "react";
import { navigate } from "../App";
import { t } from "../i18n";
import { useStore } from "../lib/store";
import { BackIcon, ColumnsIcon, HighlightIcon, LockIcon, SidebarIcon, UnlockIcon } from "./icons";
import { useNav } from "./nav";

const ZOOMS = [0.5, 0.67, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3];
const MAX_RESULTS = 30;

function PageIndicator() {
  const page = useStore((s) => s.page);
  const total = useStore((s) => s.data!.pages.length);
  const nav = useNav();
  const [editing, setEditing] = useState(false);
  if (editing) {
    return (
      <input className="page-input" autoFocus type="number" min={1} max={total} defaultValue={page} aria-label={t("go_to_page")}
        onFocus={(e) => e.target.select()} onBlur={() => setEditing(false)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            const n = Math.min(total, Math.max(1, Number((e.target as HTMLInputElement).value) || 1));
            nav.goToPage(n);
            setEditing(false);
          } else if (e.key === "Escape") setEditing(false);
        }} />
    );
  }
  return <button className="page-indicator" data-testid="page-indicator" title={t("go_to_page")} onClick={() => setEditing(true)}>{page} / {total}</button>;
}

function snippet(text: string, q: string) {
  const i = text.toLowerCase().indexOf(q);
  const start = Math.max(0, i - 30);
  return (start > 0 ? "…" : "") + text.slice(start, i + q.length + 50) + (i + q.length + 50 < text.length ? "…" : "");
}

export function BlockSearch() {
  const blocks = useStore((s) => s.data!.blocks);
  const nav = useNav();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (needle.length < 2) return [];
    const out = [];
    for (const b of blocks) {
      if (b.kind === "header_footer") continue;
      const hay = b.tr && b.tr.toLowerCase().includes(needle) ? b.tr : b.text.toLowerCase().includes(needle) ? b.text : null;
      if (hay) out.push({ b, text: snippet(hay, needle) });
      if (out.length >= MAX_RESULTS) break;
    }
    return out;
  }, [blocks, q]);

  return (
    <div className="search">
      <input ref={input} value={q} placeholder={t("search_blocks")} aria-label={t("search_blocks")}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => { if (e.key === "Escape") { setOpen(false); input.current?.blur(); } }} />
      {open && q.trim().length >= 2 && (
        <ul className="search-results">
          {results.length === 0 && <li className="empty">{t("no_results")}</li>}
          {results.map(({ b, text }) => (
            <li key={b.id} onMouseDown={(e) => { e.preventDefault(); nav.goToBlock(b.id); setOpen(false); }}>
              <span className="where">p.{b.page}</span> {text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function HeaderBar() {
  const data = useStore((s) => s.data)!;
  const setZoom = useStore((s) => s.setZoom);
  const sync = useStore((s) => s.sync);
  const showTr = useStore((s) => s.showTr);
  const sidebar = useStore((s) => s.sidebar);
  const showHl = useStore((s) => s.showHl);
  const toggle = useStore((s) => s.toggle);
  const current = useStore((s) => s.scale);
  const step = (dir: 1 | -1) => {
    const next = dir > 0 ? ZOOMS.find((z) => z > current + 0.001) : [...ZOOMS].reverse().find((z) => z < current - 0.001);
    if (next) setZoom(next);
  };
  return (
    <header className="header-bar">
      <button className="ghost" onClick={() => navigate("/")}><BackIcon />{t("back")}</button>
      <span className="title" title={data.paper.name}>{data.paper.title ?? data.paper.name}</span>
      <PageIndicator />
      <span className="group">
        <button onClick={() => step(-1)} aria-label={t("zoom_out")}>−</button>
        <span className="zoom">{Math.round(current * 100)}%</span>
        <button onClick={() => step(1)} aria-label={t("zoom_in")}>+</button>
        <button onClick={() => setZoom("fit")}>{t("fit")}</button>
      </span>
      <span className="sep" />
      <button className={`toggle${sidebar ? " on" : ""}`} onClick={() => toggle("sidebar")} title={`${t("sidebar")} ([)`} aria-pressed={sidebar}>
        <SidebarIcon />{t("sidebar")}
      </button>
      <button className={`toggle${showHl ? " on" : ""}`} onClick={() => toggle("showHl")} title={`${t("highlights")} (H)`} data-testid="toggle-hl" aria-pressed={showHl}>
        <HighlightIcon />{t("highlights")}
      </button>
      <button className={`toggle${showTr ? " on" : ""}`} onClick={() => toggle("showTr")} title={`${t("tr_panel")} (T)`} data-testid="toggle-tr" aria-pressed={showTr}>
        <ColumnsIcon />{t("tr_panel")}
      </button>
      <button className={`toggle${sync ? " on" : ""}`} onClick={() => toggle("sync")} title={`${t("sync")} (S)`} data-testid="toggle-sync" aria-pressed={sync}>
        {sync ? <LockIcon /> : <UnlockIcon />}{t("sync")}
      </button>
      <span className="sep" />
      <BlockSearch />
    </header>
  );
}
