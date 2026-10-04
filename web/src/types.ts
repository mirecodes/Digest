// Mirror of viewer.json (docs/viewer-plan.md §4.8). Keep in sync with functions/build_viewer.py.

export type Rect = [number, number, number, number];
export type Category = "problem" | "contribution" | "insight" | "method" | "result" | "limitation";
export type Column = -1 | 0 | 1;

export interface PageInfo {
  page: number;
  width: number;
  height: number;
  rotation: number;
  columns: 1 | 2;
  column_split: number | null;
  body_font_size: number;
}

export interface Block {
  id: string;
  page: number;
  kind: string;
  bbox: Rect;
  column: Column;
  order: number;
  text: string;
  translate: boolean;
  tr: string | null;
  figure_id: string | null;
}

export interface FigureNote {
  status: "OK" | "SKIP";
  reason?: string;
  ko?: { summary: string; body_md: string };
  en?: { summary: string; body_md: string };
}

export interface Figure {
  id: string;
  page: number;
  kind: "figure" | "table";
  label: string | null;
  bbox: Rect;
  caption_block: string | null;
  image_url: string;
  confidence: number;
  bbox_source: "auto" | "manual";
  refs: { page: number; block: string }[];
  note: FigureNote | null;
}

export interface Highlight {
  id: string;
  source: "evidence" | "highlight";
  category: Category;
  page: number;
  rects: Rect[];
  quote: string;
  note_ko: string | null;
  note_en: string | null;
}

export interface OutlineItem {
  title: string;
  page: number;
  level: number;
  block_id: string | null;
}

export interface ViewerData {
  version: 1;
  built_at: string;
  paper: {
    id: string;
    name: string;
    folder_rel: string;
    title: string | null;
    authors: string | null;
    venue_year: string | null;
    num_pages: number;
    pdf_url: string;
    digest_verify: "PASS" | "FAIL" | null;
  };
  pages: PageInfo[];
  blocks: Block[];
  figures: Figure[];
  highlights: Highlight[];
  evidence: Record<string, { page: number; loc: string | null; quote: string; category: string }>;
  outline: OutlineItem[];
  status: {
    layout: boolean;
    translation: { done: number; total: number };
    highlights: number;
    figure_notes: { done: number; total: number };
    annotations_verify: "PASS" | "FAIL" | null;
    warnings: number;
  };
}

export interface PaperEntry {
  id: string;
  name: string;
  folder: string;
  folder_rel: string;
  num_pages: number;
  has_report: boolean;
  digest_verify: "PASS" | "FAIL" | null;
  has_layout: boolean;
  translation: { done: number; total: number };
  highlights: number;
  figure_notes: { done: number; total: number };
  status: "ok" | "evicted";
}
