// Reader UI state shared by the panes (zustand).
import { create } from "zustand";
import type { Category, ViewerData } from "../types";

export type Zoom = number | "fit";
export type LinkTarget = { id: string; from: "pdf" | "tr" } | null;
/** The one floating panel: a figure note popover or a highlight tooltip (lib/popover.ts opens and closes it). */
export type Pop = { kind: "figure" | "highlight"; id: string; page: number; pinned: boolean } | null;
export type Tab = "outline" | "highlights" | "figures";

const storedJson = <T,>(key: string, fallback: T): T => {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
};
const persistJson = (key: string, v: unknown) => {
  try {
    localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* storage unavailable: keep the in-memory value */
  }
};

const stored = (key: string, fallback: boolean) => {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : v === "1";
  } catch {
    return fallback;
  }
};
const persist = (key: string, v: boolean) => {
  try {
    localStorage.setItem(key, v ? "1" : "0");
  } catch {
    /* storage unavailable: keep the in-memory value */
  }
};

type State = {
  data: ViewerData | null;
  zoom: Zoom;
  scale: number; // current PDF scale (px per pt), also when zoom is "fit"
  sync: boolean;
  showTr: boolean;
  sidebar: boolean;
  showHl: boolean; // highlight layer on/off (H)
  hiddenCats: Category[]; // highlight categories filtered out in the sidebar
  noteLang: "tr" | "en"; // language of figure notes and highlight notes
  tab: Tab;
  page: number;
  link: LinkTarget; // block (or figure) hovered in one pane, highlighted in the other
  flash: { id: string; n: number } | null; // brief highlight after navigation
  pop: Pop;
  setData: (d: ViewerData | null) => void;
  setZoom: (z: Zoom) => void;
  setScale: (s: number) => void;
  toggle: (key: "sync" | "showTr" | "sidebar" | "showHl") => void;
  toggleCat: (c: Category) => void;
  setNoteLang: (l: "tr" | "en") => void;
  setTab: (t: Tab) => void;
  setPage: (p: number) => void;
  setLink: (l: LinkTarget) => void;
  flashBlock: (id: string) => void;
  setPop: (p: Pop) => void;
};

export const useStore = create<State>((set, get) => ({
  data: null,
  zoom: "fit",
  scale: 1,
  sync: true,
  showTr: stored("pv.showTr", true),
  sidebar: stored("pv.sidebar", true),
  showHl: stored("pv.showHl", true),
  hiddenCats: storedJson<Category[]>("pv.hiddenCats", []),
  noteLang: storedJson<"tr" | "en">("pv.noteLang", "tr"),
  tab: "outline",
  page: 1,
  link: null,
  flash: null,
  pop: null,
  // a paper with highlights opens on its reading map
  setData: (data) => set({ data, page: 1, link: null, flash: null, pop: null, tab: data?.highlights.length ? "highlights" : "outline" }),
  setZoom: (zoom) => set({ zoom }),
  setScale: (scale) => get().scale !== scale && set({ scale }),
  toggle: (key) => {
    const v = !get()[key];
    if (key !== "sync") persist(`pv.${key}`, v);
    set({ [key]: v, ...(key === "showHl" && !v && get().pop?.kind === "highlight" ? { pop: null } : {}) } as Partial<State>);
  },
  toggleCat: (c) => {
    const cur = get().hiddenCats;
    const hiddenCats = cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c];
    persistJson("pv.hiddenCats", hiddenCats);
    set({ hiddenCats });
  },
  setNoteLang: (noteLang) => {
    persistJson("pv.noteLang", noteLang);
    set({ noteLang });
  },
  setTab: (tab) => set({ tab }),
  setPop: (pop) => set({ pop }),
  setPage: (page) => get().page !== page && set({ page }),
  setLink: (link) => {
    const cur = get().link;
    if (cur?.id !== link?.id || cur?.from !== link?.from) set({ link });
  },
  flashBlock: (id) => set({ flash: { id, n: (get().flash?.n ?? 0) + 1 } }),
}));
