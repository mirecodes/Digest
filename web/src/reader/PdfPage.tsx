// One PDF page: canvas, pdf.js text layer (selectable), and an overlay for highlights and linked/flashed blocks.
// Hover and click use hit-testing in page points (§8.2), so no overlay element blocks text selection; a click on a
// figure opens its note. Rendering goes through lib/pageRender: the text layer is built once per mount and scales
// with CSS (--total-scale-factor); the canvas is stretched by CSS while the scale changes, redrawn once it settles,
// and swapped in only when the new bitmap is done (no blank frame).
import { memo, useEffect, useRef, useState } from "react";
import { TextLayer, type PDFDocumentProxy, type RenderTask } from "pdfjs-dist";
import { clientToPt, rectStyle } from "../lib/coords";
import { union } from "../lib/highlights";
import { hitTest } from "../lib/hitTest";
import { enqueue } from "../lib/pageRender";
import { closePop, hover, pin } from "../lib/popover";
import { useStore } from "../lib/store";
import type { Block, Figure, Highlight, PageInfo } from "../types";
import { useNav } from "./nav";

type Props = { doc: PDFDocumentProxy; info: PageInfo; scale: number; blocks: Block[]; figures: Figure[]; highlights: Highlight[] };
const SETTLE_MS = 150; // redraw the canvas once the scale has not changed for this long

function PdfPage({ doc, info, scale, blocks, figures, highlights }: Props) {
  const canvasBox = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const nav = useNav();
  const setLink = useStore((s) => s.setLink);
  const link = useStore((s) => (s.link?.from === "tr" ? s.link.id : null));
  const flash = useStore((s) => s.flash);
  const [drawScale, setDrawScale] = useState(scale);
  const scaleRef = useRef(scale);
  scaleRef.current = scale;

  useEffect(() => {
    if (scale === drawScale) return;
    const id = setTimeout(() => setDrawScale(scale), SETTLE_MS);
    return () => clearTimeout(id);
  }, [scale, drawScale]);

  useEffect(() => {
    let task: RenderTask | null = null;
    let cancelled = false;
    const box = canvasBox.current!;
    const canvas = document.createElement("canvas");
    const drop = enqueue(info.page, 0, async () => {
      const page = await doc.getPage(info.page);
      if (cancelled) return;
      const viewport = page.getViewport({ scale: drawScale });
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      task = page.render({ canvas, viewport, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined });
      await task.promise;
      for (const old of box.querySelectorAll("canvas")) old.width = old.height = 0; // release the old bitmap
      box.replaceChildren(canvas);
    });
    return () => {
      cancelled = true;
      drop();
      task?.cancel();
      if (!canvas.isConnected) canvas.width = canvas.height = 0;
    };
  }, [doc, info.page, drawScale]);
  useEffect(() => {
    const box = canvasBox.current!;
    return () => box.querySelectorAll("canvas").forEach((c) => (c.width = c.height = 0)); // release on unmount
  }, []);

  useEffect(() => {
    let text: TextLayer | null = null;
    let cancelled = false;
    const container = textRef.current!;
    const drop = enqueue(info.page, 1, async () => {
      const page = await doc.getPage(info.page);
      if (cancelled) return;
      container.replaceChildren();
      text = new TextLayer({ textContentSource: page.streamTextContent(), container, viewport: page.getViewport({ scale: scaleRef.current }) });
      await text.render();
    });
    return () => {
      cancelled = true;
      drop();
      text?.cancel();
    };
  }, [doc, info.page]);

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
      wrapRef.current.classList.toggle("over-figure", linked?.type === "figure");
      const over = linked?.type === "figure" ? null : hitTest(x, y, { highlights }); // figures open on click
      hover(over ? { kind: "highlight", id: over.id, page: info.page } : null);
    });
  };
  const onLeave = () => {
    cancelAnimationFrame(frame.current);
    if (useStore.getState().link?.from === "pdf") setLink(null);
    wrapRef.current?.classList.remove("over-figure");
    hover(null);
  };
  const onClick = (e: React.MouseEvent) => {
    const [x, y] = pt(e);
    const hit = hitTest(x, y, { figures, blocks });
    if (e.altKey) {
      if (hit) nav.showInTranslation(hit.id);
      return;
    }
    if (window.getSelection()?.isCollapsed === false) return; // the end of a text selection, not a click
    const pop = useStore.getState().pop;
    if (hit?.type === "figure" && !(pop?.pinned && pop.id === hit.id)) pin({ kind: "figure", id: hit.id, page: info.page });
    else if (pop?.pinned) closePop(); // a second click on the figure, or a click elsewhere on the page
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
      <div ref={canvasBox} className="pdf-canvas" />
      <div className="overlay">
        {highlights.map((h) =>
          h.rects.map((r, i) => <div key={`${h.id}-${i}`} className={`hl hl-${h.category}`} data-hl-id={h.id} style={rectStyle(r, scale)} />),
        )}
        {figures.map((f) => f.confidence < 0.6 && <div key={f.id} className="fig-lowconf" style={rectStyle(f.bbox, scale)} />)}
        {linkRect && <div className="block-link" data-block-id={link} style={rectStyle(linkRect, scale)} />}
        {flashRect && <div key={flash!.n} className="flash" style={rectStyle(flashRect, scale)} />}
      </div>
      <div ref={textRef} className="textLayer" />
    </div>
  );
}

export default memo(PdfPage);
