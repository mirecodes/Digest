// The floating panel: figure note popover or highlight tooltip (§8.6-8.7). Fixed to the viewport, so it can float
// over the translation pane; it follows its anchor while the PDF pane scrolls. Placement: lib/popover.placePanel.
import { useEffect, useLayoutEffect, useReducer, useRef, useState } from "react";
import { t, type Key } from "../i18n";
import { parseCitations } from "../lib/citations";
import { union } from "../lib/highlights";
import { closePop, enterPanel, leavePanel, placePanel, type Box } from "../lib/popover";
import { useStore } from "../lib/store";
import type { Figure, Highlight, Rect } from "../types";
import { useNav } from "./nav";

const MAX_W = 420;
const TIP_W = 320;

export function CitationText({ text }: { text: string }) {
  const evidence = useStore((s) => s.data!.evidence);
  const nav = useNav();
  return (
    <>
      {parseCitations(text).map((s, i) => {
        if (s.type === "text") return <span key={i}>{s.text}</span>;
        if (s.type === "cite") {
          const e = s.eid ? evidence[s.eid] : undefined;
          return (
            <button key={i} className="cite" title={e ? `"${e.quote}"` : s.eid ?? `p.${s.page}`}
              onClick={() => nav.goToPage(s.page ?? e?.page ?? 1)}>
              {[s.eid, s.page ? `p.${s.page}` : ""].filter(Boolean).join(", ")}
            </button>
          );
        }
        return <span key={i} className="tag" title={s.arg || undefined}>{s.tag === "FIG" ? "FIG" : s.tag}</span>;
      })}
    </>
  );
}

/** body_md: "- " lines become a list, other lines paragraphs. */
function NoteBody({ md }: { md: string }) {
  const out: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) out.push(<ul key={out.length}>{bullets.map((b, i) => <li key={i}><CitationText text={b} /></li>)}</ul>);
    bullets = [];
  };
  for (const line of md.split("\n").map((l) => l.trim()).filter(Boolean)) {
    if (/^[-*] /.test(line)) bullets.push(line.slice(2));
    else {
      flush();
      out.push(<p key={out.length}><CitationText text={line} /></p>);
    }
  }
  flush();
  return <>{out}</>;
}

function LangToggle({ has }: { has: { tr: boolean; en: boolean } }) {
  const lang = useStore((s) => s.data!.lang);
  const noteLang = useStore((s) => s.noteLang);
  const setNoteLang = useStore((s) => s.setNoteLang);
  if (!has.tr || !has.en || lang === "en") return null;
  return (
    <span className="lang-toggle" role="group">
      {(["tr", "en"] as const).map((l) => (
        <button key={l} className={noteLang === l ? "on" : ""} aria-pressed={noteLang === l} onClick={() => setNoteLang(l)}>
          {l === "tr" ? lang.toUpperCase() : "EN"}
        </button>
      ))}
    </span>
  );
}

function FigureNote({ f, pinned }: { f: Figure; pinned: boolean }) {
  const noteLang = useStore((s) => s.noteLang);
  const note = f.note;
  const ok = note?.status === "OK";
  const body = ok ? (noteLang === "en" ? note.en ?? note.tr : note.tr ?? note.en) : undefined;
  return (
    <>
      <header>
        <strong>{f.label ?? (f.kind === "table" ? "Table" : "Figure")}</strong>
        <span className="where">p.{f.page}</span>
        <span className="spacer" />
        {ok && <LangToggle has={{ tr: !!note.tr, en: !!note.en }} />}
        {pinned && <button className="icon ghost" aria-label={t("close")} onClick={closePop}>×</button>}
      </header>
      {body ? (
        <>
          {body.summary && <p className="summary"><CitationText text={body.summary} /></p>}
          <NoteBody md={body.body_md} />
        </>
      ) : (
        <p className="muted">{note?.status === "SKIP" ? `${t("note_skipped")}${note.reason ? ` — ${note.reason}` : ""}` : t("no_note")}</p>
      )}
      {f.confidence < 0.6 && <p className="muted warn">{t("low_conf")}</p>}
      {!pinned && <p className="hint">{t("pin_hint")}</p>}
    </>
  );
}

function HighlightTip({ h }: { h: Highlight }) {
  const noteLang = useStore((s) => s.noteLang);
  const note = noteLang === "en" ? h.note_en ?? h.note_tr : h.note_tr ?? h.note_en;
  return (
    <>
      <header>
        <span className={`swatch hl-${h.category}`} />
        <strong>{t(`cat_${h.category}` as Key)}</strong>
        <span className="where">p.{h.page}</span>
      </header>
      {note && <p>{note}</p>}
    </>
  );
}

type Props = {
  clientBox: (page: number, r: Rect) => Box | null; // viewport box of a page rect
  scroller: React.RefObject<HTMLElement | null>; // the PDF pane: re-place while it scrolls
};

export default function Popover({ clientBox, scroller }: Props) {
  const pop = useStore((s) => s.pop);
  const data = useStore((s) => s.data)!;
  const ref = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  const [, rerender] = useReducer((n: number) => n + 1, 0);

  useEffect(() => {
    if (!pop) return;
    let frame = 0;
    const onMove = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(rerender);
    };
    const el = scroller.current;
    el?.addEventListener("scroll", onMove, { passive: true });
    window.addEventListener("resize", onMove);
    return () => {
      cancelAnimationFrame(frame);
      el?.removeEventListener("scroll", onMove);
      window.removeEventListener("resize", onMove);
    };
  }, [pop, scroller]);
  useLayoutEffect(() => {
    const h = ref.current?.offsetHeight ?? 0; // measured before paint, so the first frame is already placed
    if (h !== height) setHeight(h);
  });

  useEffect(() => {
    if (!pop?.pinned) return;
    const outside = (e: PointerEvent) => {
      const el = e.target as Element;
      if (!ref.current?.contains(el) && !el.closest?.(".fig-badge")) closePop();
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [pop?.pinned]);

  if (!pop) return null;
  const fig = pop.kind === "figure" ? data.figures.find((f) => f.id === pop.id) : undefined;
  const hl = pop.kind === "highlight" ? data.highlights.find((h) => h.id === pop.id) : undefined;
  if (!fig && !hl) return null;

  const a = clientBox(pop.page, fig ? fig.bbox : union(hl!.rects));
  if (!a) return null;
  const w = Math.min(fig ? MAX_W : TIP_W, window.innerWidth - 24);
  const style = { ...placePanel(a, w, height, window.innerWidth, window.innerHeight, !!fig), width: w };

  return (
    <div ref={ref} className={`popover ${fig ? "fig-pop" : "hl-tip"}${pop.pinned ? " pinned" : ""}`} style={style}
      data-testid={fig ? "figure-popover" : "highlight-tip"} data-pinned={pop.pinned} role="dialog"
      aria-label={fig?.label ?? hl?.category} onPointerEnter={enterPanel} onPointerLeave={leavePanel}>
      {fig ? <FigureNote f={fig} pinned={pop.pinned} /> : <HighlightTip h={hl!} />}
    </div>
  );
}
