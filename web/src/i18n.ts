// UI strings. Korean is the default; set localStorage "pv.lang" to "en" for English.
const ko = {
  library: "내 논문",
  library_sub: "정리된 논문을 원문과 번역으로 나란히 읽어요.",
  search_papers: "논문 이름으로 찾기",
  pages: "페이지",
  open: "열기",
  no_papers: "아직 논문이 없어요. scripts/digest.sh로 먼저 정리해 주세요.",
  evicted: "iCloud에서 내려받지 않음",
  translation: "번역",
  highlights: "하이라이트",
  figure_notes: "피규어 해설",
  back: "내 논문",
  fit: "맞춤",
  zoom_in: "확대",
  zoom_out: "축소",
  tr_panel: "번역 패널",
  sync: "싱크",
  sidebar: "사이드바",
  outline: "아웃라인",
  no_outline: "아웃라인 없음",
  search_blocks: "블록 검색 (/)",
  no_results: "결과 없음",
  go_to_page: "페이지로 이동",
  loading: "불러오는 중…",
  load_failed: "불러오기 실패",
  untranslated: "번역 없음 — 원문 표시",
};
export type Key = keyof typeof ko;
const en: Record<Key, string> = {
  library: "My papers",
  library_sub: "Read digested papers side by side with their translation.",
  search_papers: "Find a paper by name",
  pages: "pages",
  open: "Open",
  no_papers: "No papers yet. Run scripts/digest.sh first.",
  evicted: "Not downloaded from iCloud",
  translation: "Translation",
  highlights: "Highlights",
  figure_notes: "Figure notes",
  back: "My papers",
  fit: "Fit",
  zoom_in: "Zoom in",
  zoom_out: "Zoom out",
  tr_panel: "Translation pane",
  sync: "Sync",
  sidebar: "Sidebar",
  outline: "Outline",
  no_outline: "No outline",
  search_blocks: "Search blocks (/)",
  no_results: "No results",
  go_to_page: "Go to page",
  loading: "Loading…",
  load_failed: "Failed to load",
  untranslated: "Not translated — showing the original",
};

let lang: "ko" | "en" = "ko";
try {
  if (localStorage.getItem("pv.lang") === "en") lang = "en";
} catch {
  /* default ko */
}

export const t = (key: Key): string => (lang === "en" ? en : ko)[key];
