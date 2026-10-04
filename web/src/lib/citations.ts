// Citation markers in pre-generated notes (docs/viewer-plan.md §8.9): [E12, p.6] links to evidence,
// [FIG: fig-p3-0], [CALC: ...], [INTERP], [EXT] become small badges.
export type Segment =
  | { type: "text"; text: string }
  | { type: "cite"; eid: string; page: number | null }
  | { type: "tag"; tag: "FIG" | "CALC" | "INTERP" | "EXT"; arg: string };

const MARKER_RE = /\[(E\d+)(?:\s*,\s*p\.\s*(\d+))?\]|\[(FIG|CALC):\s*([^\]]*)\]|\[(INTERP|EXT)\]/g;

export function parseCitations(text: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(MARKER_RE)) {
    if (m.index > last) out.push({ type: "text", text: text.slice(last, m.index) });
    if (m[1]) out.push({ type: "cite", eid: m[1], page: m[2] ? Number(m[2]) : null });
    else if (m[3]) out.push({ type: "tag", tag: m[3] as "FIG" | "CALC", arg: m[4].trim() });
    else out.push({ type: "tag", tag: m[5] as "INTERP" | "EXT", arg: "" });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ type: "text", text: text.slice(last) });
  return out;
}
