// Translation pane: one card per original page, same gap as the PDF pane. Card positions are measured and
// reported as a PaneLayout for scroll sync.
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { PAGE_GAP, PANE_PAD } from "../lib/coords";
import { categoryByBlock, visible } from "../lib/highlights";
import type { PaneLayout } from "../lib/scrollSync";
import { useStore } from "../lib/store";
import type { Block, Figure } from "../types";
import TranslationPage from "./TranslationPage";

type Props = { elRef: React.RefObject<HTMLDivElement | null>; onLayout: (layout: PaneLayout) => void };

export default function TranslationPane({ elRef, onLayout }: Props) {
  const data = useStore((s) => s.data)!;
  const [width, setWidth] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);

  const showHl = useStore((s) => s.showHl);
  const hiddenCats = useStore((s) => s.hiddenCats);
  const byPage = useMemo(() => {
    const m = new Map<number, { blocks: Block[]; figures: Figure[] }>();
    for (const p of data.pages) m.set(p.page, { blocks: [], figures: [] });
    for (const b of data.blocks) m.get(b.page)?.blocks.push(b);
    for (const f of data.figures) m.get(f.page)?.figures.push(f);
    return m;
  }, [data]);
  // one map for all pages; TranslationPage reads its own blocks from it (memo stays valid for unchanged pages)
  const hlCats = useMemo(() => categoryByBlock(visible(data.highlights, showHl, hiddenCats), data.blocks),
    [data, showHl, hiddenCats]);

  useLayoutEffect(() => {
    const el = elRef.current!;
    const content = contentRef.current!;
    const measure = () => {
      setWidth(el.clientWidth);
      const cards = [...content.children] as HTMLElement[];
      onLayout({ tops: cards.map((c) => c.offsetTop), heights: cards.map((c) => c.offsetHeight), gap: PAGE_GAP });
    };
    const ro = new ResizeObserver(measure); // pane width, and content height (any card resizing)
    ro.observe(el);
    ro.observe(content);
    measure();
    return () => ro.disconnect();
  }, [elRef, onLayout, data]);

  const inner = Math.max(0, width - 2 * PANE_PAD);
  return (
    <div ref={elRef} className="pane tr-pane" tabIndex={0} data-testid="tr-pane">
      <div ref={contentRef} className="tr-content" style={{ width: inner }}>
        {inner > 0 &&
          data.pages.map((p) => (
            <TranslationPage key={p.page} paperId={data.paper.id} info={p} s={inner / p.width}
              blocks={byPage.get(p.page)!.blocks} figures={byPage.get(p.page)!.figures} hlCats={hlCats} />
          ))}
      </div>
    </div>
  );
}
