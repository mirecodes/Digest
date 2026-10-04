// Sidebar (Phase 2: outline tab only; highlights, figures, notes and chats come in later phases).
import { t } from "../i18n";
import { useStore } from "../lib/store";
import { useNav } from "./nav";

export default function Sidebar() {
  const outline = useStore((s) => s.data!.outline);
  const page = useStore((s) => s.page);
  const nav = useNav();
  return (
    <aside className="sidebar">
      <div className="tabs"><span className="tab on">{t("outline")}</span></div>
      {outline.length === 0 && <p className="empty">{t("no_outline")}</p>}
      <ul className="outline">
        {outline.map((o, i) => (
          <li key={i} className={o.page === page ? "here" : ""} style={{ paddingLeft: 8 + (o.level - 1) * 12 }}>
            <button onClick={() => (o.block_id ? nav.goToBlock(o.block_id) : nav.goToPage(o.page))}>
              {o.title} <span className="where">{o.page}</span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
