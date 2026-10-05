// Citation markers in pre-generated notes (docs/viewer-plan.md §8.9): [E12, p.6] links to evidence, [p.6] to a page
// (notes written without evidence.md), [FIG: fig-p3-0], [CALC: ...], [INTERP], [EXT] become small badges.
export type Segment =
  | { type: "text"; text: string }
  | { type: "cite"; eid: string | null; page: number | null }
  | { type: "tag"; tag: "FIG" | "CALC" | "INTERP" | "EXT"; arg: string };

const MARKER_RE = /\[(E\d+)(?:\s*,\s*p\.\s*(\d+))?\]|\[(FIG|CALC):\s*([^\]]*)\]|\[(INTERP|EXT)\]|\[p\.\s*(\d+)\]/g;

export function parseCitations(text: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(MARKER_RE)) {
    if (m.index > last) out.push({ type: "text", text: text.slice(last, m.index) });
    if (m[1]) out.push({ type: "cite", eid: m[1], page: m[2] ? Number(m[2]) : null });
    else if (m[3]) out.push({ type: "tag", tag: m[3] as "FIG" | "CALC", arg: m[4].trim() });
    else if (m[5]) out.push({ type: "tag", tag: m[5] as "INTERP" | "EXT", arg: "" });
    else out.push({ type: "cite", eid: null, page: Number(m[6]) });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ type: "text", text: text.slice(last) });
  return out;
}
