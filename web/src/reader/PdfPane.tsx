// Original PDF pane. All page placeholders are laid out at their exact size up front (sizes come from
// viewer.json); only pages near the viewport render a canvas and text layer (§8.2, lib/pageRender.keepRange).
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { PAGE_GAP, PANE_PAD, stackTops } from "../lib/coords";
import { mapRef, pageAt, refPage, type PaneLayout } from "../lib/scrollSync";
import { visible } from "../lib/highlights";
import { keepRange } from "../lib/pageRender";
import { useStore } from "../lib/store";
import type { Block, Figure, Highlight, Rect } from "../types";
import PdfPage from "./PdfPage";
import Popover from "./Popover";

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
  const [range, setRange] = useState<[number, number]>([0, 2]);

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

  const showHl = useStore((s) => s.showHl);
  const hiddenCats = useStore((s) => s.hiddenCats);
  const byPage = useMemo(() => {
    const m = new Map<number, { blocks: Block[]; figures: Figure[]; highlights: Highlight[] }>();
    for (const p of data.pages) m.set(p.page, { blocks: [], figures: [], highlights: [] });
    for (const b of data.blocks) m.get(b.page)?.blocks.push(b);
    for (const f of data.figures) m.get(f.page)?.figures.push(f);
    for (const h of visible(data.highlights, showHl, hiddenCats)) m.get(h.page)?.highlights.push(h);
    return m;
  }, [data, showHl, hiddenCats]);
  const pageLeft = (i: number) => Math.max(PANE_PAD, (width - data.pages[i].width * scale) / 2);
  const clientBox = (page: number, r: Rect) => {
    const b = elRef.current?.querySelector(`.pdf-page[data-page="${page}"]`)?.getBoundingClientRect();
    return b ? { left: b.left + r[0] * scale, top: b.top + r[1] * scale, right: b.left + r[2] * scale, bottom: b.top + r[3] * scale } : null;
  };

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
      setRange((r) => {
        const next = keepRange(r, first, last, data.pages.length);
        return r[0] === next[0] && r[1] === next[1] ? r : next;
      });
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
              style={{ top: layout.tops[i], width: w, height: layout.heights[i], left: pageLeft(i) }}>
              {i >= range[0] && i <= range[1] && width > 0 && (
                <PdfPage doc={doc} info={p} scale={scale} {...byPage.get(p.page)!} />
              )}
            </div>
          );
        })}
        {width > 0 && <Popover clientBox={clientBox} scroller={elRef} />}
      </div>
    </div>
  );
}
