// Original PDF pane. All page placeholders are laid out at their exact size up front (sizes come from
// viewer.json); only pages within ±2 of the viewport render a canvas and text layer (§8.2).
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { PAGE_GAP, PANE_PAD, stackTops } from "../lib/coords";
import { mapRef, pageAt, refPage, type PaneLayout } from "../lib/scrollSync";
import { useStore } from "../lib/store";
import type { Block, Figure } from "../types";
import PdfPage from "./PdfPage";

const RENDER_MARGIN = 2; // pages rendered beyond the visible ones

type Props = {
  doc: PDFDocumentProxy;
  elRef: React.RefObject<HTMLDivElement | null>;
  onLayout: (layout: PaneLayout, scale: number) => void;
};

export default function PdfPane({ doc, elRef, onLayout }: Props) {
  const data = useStore((s) => s.data)!;
  const zoom = useStore((s) => s.zoom);
  const setPage = useStore((s) => s.setPage);
  const [width, setWidth] = useState(0);
  const [range, setRange] = useState<[number, number]>([0, RENDER_MARGIN]);

  useLayoutEffect(() => {
    const el = elRef.current!;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, [elRef]);

  const maxWidth = Math.max(...data.pages.map((p) => p.width));
  const scale = zoom === "fit" ? Math.max(0.2, (width - 2 * PANE_PAD) / maxWidth) : zoom;
  const layout = useMemo<PaneLayout>(() => {
    const heights = data.pages.map((p) => p.height * scale);
    return { tops: stackTops(heights), heights, gap: PAGE_GAP };
  }, [data.pages, scale]);
  const total = layout.tops.length ? layout.tops[layout.tops.length - 1] + layout.heights[layout.heights.length - 1] + PANE_PAD : 0;

  const byPage = useMemo(() => {
    const m = new Map<number, { blocks: Block[]; figures: Figure[] }>();
    for (const p of data.pages) m.set(p.page, { blocks: [], figures: [] });
    for (const b of data.blocks) m.get(b.page)?.blocks.push(b);
    for (const f of data.figures) m.get(f.page)?.figures.push(f);
    return m;
  }, [data]);

  // keep the reading position when the scale changes (zoom, resize)
  const prev = useRef<PaneLayout | null>(null);
  useLayoutEffect(() => {
    const el = elRef.current!;
    if (width === 0) return; // not measured yet
    if (prev.current) {
      const ref = 0.3 * el.clientHeight;
      el.scrollTop = mapRef(el.scrollTop + ref, prev.current, layout) - ref;
    }
    prev.current = layout;
    onLayout(layout, scale);
  }, [layout, scale, width, elRef, onLayout]);

  useEffect(() => {
    const el = elRef.current!;
    let frame = 0;
    const update = () => {
      const first = pageAt(el.scrollTop, layout);
      const last = pageAt(el.scrollTop + el.clientHeight, layout);
      const next: [number, number] = [Math.max(0, first - RENDER_MARGIN), Math.min(data.pages.length - 1, last + RENDER_MARGIN)];
      setRange((r) => (r[0] === next[0] && r[1] === next[1] ? r : next));
      setPage(refPage(el, layout));
    };
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(update);
    };
    update();
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      el.removeEventListener("scroll", onScroll);
    };
  }, [elRef, layout, data.pages.length, setPage]);

  return (
    <div ref={elRef} className="pane pdf-pane" tabIndex={0} data-testid="pdf-pane">
      <div className="pane-content" style={{ height: total }}>
        {data.pages.map((p, i) => {
          const w = p.width * scale;
          return (
            <div key={p.page} className="pdf-page" data-page={p.page}
              style={{ top: layout.tops[i], width: w, height: layout.heights[i], left: Math.max(PANE_PAD, (width - w) / 2) }}>
              {i >= range[0] && i <= range[1] && width > 0 && (
                <PdfPage doc={doc} info={p} scale={scale} blocks={byPage.get(p.page)!.blocks} figures={byPage.get(p.page)!.figures} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
