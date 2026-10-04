// Sidebar tabs: outline, highlights (layer switch, category filter with counts, list by category then page),
// figures (click: scroll there and pin its note). Notes and chats come in later phases.
import { useMemo } from "react";
import { t, type Key } from "../i18n";
import { CATEGORIES } from "../lib/highlights";
import { pin } from "../lib/popover";
import { useStore, type Tab } from "../lib/store";
import { useNav } from "./nav";

const QUOTE_MAX = 110;

function Outline() {
  const outline = useStore((s) => s.data!.outline);
  const page = useStore((s) => s.page);
  const nav = useNav();
  if (outline.length === 0) return <p className="empty">{t("no_outline")}</p>;
  return (
    <ul className="outline">
      {outline.map((o, i) => (
        <li key={i} className={o.page === page ? "here" : ""} style={{ paddingLeft: 8 + (o.level - 1) * 12 }}>
          <button onClick={() => (o.block_id ? nav.goToBlock(o.block_id) : nav.goToPage(o.page))}>
            {o.title} <span className="where">{o.page}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** The paper's reading map: one-line summaries (notes) grouped by category, each anchored to its sentence. */
function Highlights() {
  const highlights = useStore((s) => s.data!.highlights);
  const noteLang = useStore((s) => s.noteLang);
  const showHl = useStore((s) => s.showHl);
  const hidden = useStore((s) => s.hiddenCats);
  const toggle = useStore((s) => s.toggle);
  const toggleCat = useStore((s) => s.toggleCat);
  const nav = useNav();
  const byCat = useMemo(
    () => CATEGORIES.map((c) => ({ c, items: highlights.filter((h) => h.category === c).sort((a, b) => a.page - b.page) })),
    [highlights],
  );
  if (highlights.length === 0) return <p className="empty">{t("no_highlights")}</p>;
  return (
    <div className="hl-panel">
      <p className="panel-title">{t("key_points")}</p>
      <label className="check main">
        <input type="checkbox" checked={showHl} onChange={() => toggle("showHl")} data-testid="toggle-hl-side" />
        {t("show_highlights")} <span className="where">H</span>
      </label>
      <div className="cats">
        {byCat.filter(({ items }) => items.length).map(({ c, items }) => (
          <label key={c} className="check">
            <input type="checkbox" checked={!hidden.includes(c)} disabled={!showHl} onChange={() => toggleCat(c)} />
            <span className={`swatch hl-${c}`} />
            {t(`cat_${c}` as Key)} <span className="where">{items.length}</span>
          </label>
        ))}
      </div>
      {showHl && byCat.filter(({ c, items }) => items.length && !hidden.includes(c)).map(({ c, items }) => (
        <section key={c}>
          <h3><span className={`swatch hl-${c}`} />{t(`cat_${c}` as Key)}</h3>
          <ul className="hl-list">
            {items.map((h) => {
              const note = noteLang === "en" ? h.note_en ?? h.note_tr : h.note_tr ?? h.note_en;
              const quote = h.quote.length > QUOTE_MAX ? `${h.quote.slice(0, QUOTE_MAX)}…` : h.quote;
              return (
                <li key={h.id}>
                  <button data-hl-item={h.id} onClick={() => nav.goToBlock(h.id)}>
                    <span className="hl-text">
                      <span className="hl-note">{note ?? quote}</span>
                      {note && <span className="hl-quote">“{quote}”</span>}
                    </span>
                    <span className="where">p.{h.page}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

function Figures() {
  const figures = useStore((s) => s.data!.figures);
  const nav = useNav();
  if (figures.length === 0) return <p className="empty">{t("no_figures")}</p>;
  return (
    <ul className="fig-list">
      {figures.map((f) => (
        <li key={f.id}>
          <button onClick={() => { nav.goToBlock(f.id); pin({ kind: "figure", id: f.id, page: f.page }); }}>
            <img src={f.image_url} alt="" loading="lazy" />
            <span className="fig-meta">
              <strong>{f.label ?? f.id}</strong>
              <span className="where">p.{f.page}{f.note?.status === "OK" ? "" : " · —"}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

const TABS: { id: Tab; label: Key }[] = [
  { id: "outline", label: "outline" },
  { id: "highlights", label: "highlights" },
  { id: "figures", label: "figures" },
];

export default function Sidebar() {
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);
  return (
    <aside className="sidebar">
      <div className="tabs" role="tablist">
        {TABS.map(({ id, label }) => (
          <button key={id} role="tab" aria-selected={tab === id} className={`tab${tab === id ? " on" : ""}`} onClick={() => setTab(id)}>
            {t(label)}
          </button>
        ))}
      </div>
      {tab === "outline" && <Outline />}
      {tab === "highlights" && <Highlights />}
      {tab === "figures" && <Figures />}
    </aside>
  );
}
