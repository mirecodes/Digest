// One PDF page: canvas, pdf.js text layer (selectable), and an overlay for highlights, figure badges and
// linked/flashed blocks. Hover uses hit-testing in page points (§8.2), so no overlay element blocks text selection
// (only the small ⓘ badges take pointer events).
import { memo, useEffect, useRef } from "react";
import { TextLayer, type PDFDocumentProxy, type RenderTask } from "pdfjs-dist";
import { clientToPt, rectStyle } from "../lib/coords";
import { union } from "../lib/highlights";
import { hitTest } from "../lib/hitTest";
import { hover, pin } from "../lib/popover";
import { useStore } from "../lib/store";
import type { Block, Figure, Highlight, PageInfo } from "../types";
import { useNav } from "./nav";

type Props = { doc: PDFDocumentProxy; info: PageInfo; scale: number; blocks: Block[]; figures: Figure[]; highlights: Highlight[] };
const BADGE = 22; // px, ⓘ badge at the figure's bottom-right corner

function PdfPage({ doc, info, scale, blocks, figures, highlights }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const nav = useNav();
  const setLink = useStore((s) => s.setLink);
  const link = useStore((s) => (s.link?.from === "tr" ? s.link.id : null));
  const flash = useStore((s) => s.flash);

  useEffect(() => {
    let task: RenderTask | null = null;
    let text: TextLayer | null = null;
    let cancelled = false;
    const canvas = canvasRef.current!;
    const container = textRef.current!;
    doc.getPage(info.page).then((page) => {
      if (cancelled) return;
      const viewport = page.getViewport({ scale });
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      task = page.render({ canvas, viewport, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined });
      task.promise.catch(() => {}); // cancelled renders reject
      container.replaceChildren();
      text = new TextLayer({ textContentSource: page.streamTextContent(), container, viewport });
      text.render().catch(() => {});
    });
    return () => {
      cancelled = true;
      task?.cancel();
      text?.cancel();
      canvas.width = canvas.height = 0; // release the bitmap right away
    };
  }, [doc, info.page, scale]);

  const pt = (e: { clientX: number; clientY: number }) =>
    clientToPt(e.clientX, e.clientY, wrapRef.current!.getBoundingClientRect(), scale);
  const frame = useRef(0);
  const onMove = (e: React.PointerEvent) => {
    const { clientX, clientY } = e;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      if (!wrapRef.current) return;
      const [x, y] = pt({ clientX, clientY });
      const linked = hitTest(x, y, { figures, blocks });
      setLink(linked ? { id: linked.id, from: "pdf" } : null);
      const over = hitTest(x, y, { figures, highlights });
      hover(over && over.type !== "block" ? { kind: over.type, id: over.id, page: info.page } : null);
    });
  };
  const onLeave = () => {
    cancelAnimationFrame(frame.current);
    if (useStore.getState().link?.from === "pdf") setLink(null);
    hover(null);
  };
  const onClick = (e: React.MouseEvent) => {
    const [x, y] = pt(e);
    const hit = hitTest(x, y, { figures, blocks });
    if (e.altKey) {
      if (hit) nav.showInTranslation(hit.id);
    } else if (hit?.type === "figure" && window.getSelection()?.isCollapsed !== false) {
      pin({ kind: "figure", id: hit.id, page: info.page }); // a plain click inside a figure pins its note
    }
  };

  const findRect = (id: string | undefined) => {
    if (!id) return undefined;
    const hl = highlights.find((h) => h.id === id);
    return blocks.find((b) => b.id === id)?.bbox ?? figures.find((f) => f.id === id)?.bbox ?? (hl && union(hl.rects));
  };
  const linkRect = findRect(link ?? undefined);
  const flashRect = findRect(flash?.id);

  return (
    <div ref={wrapRef} className="pdf-page-inner" style={{ "--total-scale-factor": scale } as React.CSSProperties}
      onPointerMove={onMove} onPointerLeave={onLeave} onClick={onClick}>
      <canvas ref={canvasRef} style={{ width: info.width * scale, height: info.height * scale }} />
      <div className="overlay">
        {highlights.map((h) =>
          h.rects.map((r, i) => <div key={`${h.id}-${i}`} className={`hl hl-${h.category}`} data-hl-id={h.id} style={rectStyle(r, scale)} />),
        )}
        {figures.map((f) => {
          const [, , x1, y1] = f.bbox;
          const target = { kind: "figure" as const, id: f.id, page: info.page };
          return (
            <div key={f.id}>
              {f.confidence < 0.6 && <div className="fig-lowconf" style={rectStyle(f.bbox, scale)} />}
              <button className={`fig-badge${f.note?.status === "OK" ? " has-note" : ""}`} data-figure-id={f.id}
                aria-label={f.label ?? f.id} title={f.label ?? undefined}
                style={{ left: x1 * scale - BADGE - 4, top: y1 * scale - BADGE - 4 }}
                onPointerEnter={() => hover(target, true)}
                onClick={(e) => { e.stopPropagation(); pin(target); }}>
                {f.confidence < 0.6 ? "?" : "i"}
              </button>
            </div>
          );
        })}
        {linkRect && <div className="block-link" data-block-id={link} style={rectStyle(linkRect, scale)} />}
        {flashRect && <div key={flash!.n} className="flash" style={rectStyle(flashRect, scale)} />}
      </div>
      <div ref={textRef} className="textLayer" />
    </div>
  );
}

export default memo(PdfPage);
