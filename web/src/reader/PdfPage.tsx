// One PDF page: canvas, pdf.js text layer (selectable), and an overlay for linked/flashed blocks.
// Hover uses hit-testing in page points (§8.2), so no overlay element blocks text selection.
import { memo, useEffect, useRef } from "react";
import { TextLayer, type PDFDocumentProxy, type RenderTask } from "pdfjs-dist";
import { clientToPt, rectStyle } from "../lib/coords";
import { hitTest } from "../lib/hitTest";
import { useStore } from "../lib/store";
import type { Block, Figure, PageInfo } from "../types";
import { useNav } from "./nav";

type Props = { doc: PDFDocumentProxy; info: PageInfo; scale: number; blocks: Block[]; figures: Figure[] };

function PdfPage({ doc, info, scale, blocks, figures }: Props) {
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

  const hitAt = (e: React.PointerEvent | React.MouseEvent) => {
    const [x, y] = clientToPt(e.clientX, e.clientY, wrapRef.current!.getBoundingClientRect(), scale);
    return hitTest(x, y, { figures, blocks });
  };
  const frame = useRef(0);
  const onMove = (e: React.PointerEvent) => {
    const { clientX, clientY } = e;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      if (!wrapRef.current) return;
      const hit = hitAt({ clientX, clientY } as React.PointerEvent);
      setLink(hit && hit.type !== "highlight" ? { id: hit.id, from: "pdf" } : null);
    });
  };
  const onLeave = () => {
    cancelAnimationFrame(frame.current);
    if (useStore.getState().link?.from === "pdf") setLink(null);
  };
  const onClick = (e: React.MouseEvent) => {
    if (!e.altKey) return; // plain clicks are for text selection
    const hit = hitAt(e);
    if (hit && hit.type !== "highlight") nav.showInTranslation(hit.id);
  };

  const findRect = (id: string | undefined) =>
    id ? (blocks.find((b) => b.id === id)?.bbox ?? figures.find((f) => f.id === id)?.bbox) : undefined;
  const linkRect = findRect(link ?? undefined);
  const flashRect = findRect(flash?.id);

  return (
    <div ref={wrapRef} className="pdf-page-inner" style={{ "--total-scale-factor": scale } as React.CSSProperties}
      onPointerMove={onMove} onPointerLeave={onLeave} onClick={onClick}>
      <canvas ref={canvasRef} style={{ width: info.width * scale, height: info.height * scale }} />
      <div className="overlay">
        {linkRect && <div className="block-link" data-block-id={link} style={rectStyle(linkRect, scale)} />}
        {flashRect && <div key={flash!.n} className="flash" style={rectStyle(flashRect, scale)} />}
      </div>
      <div ref={textRef} className="textLayer" />
    </div>
  );
}

export default memo(PdfPage);
