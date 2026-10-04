// Reader UI state shared by the panes (zustand).
import { create } from "zustand";
import type { ViewerData } from "../types";

export type Zoom = number | "fit";
export type LinkTarget = { id: string; from: "pdf" | "tr" } | null;

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
  page: number;
  link: LinkTarget; // block (or figure) hovered in one pane, highlighted in the other
  flash: { id: string; n: number } | null; // brief highlight after navigation
  setData: (d: ViewerData | null) => void;
  setZoom: (z: Zoom) => void;
  setScale: (s: number) => void;
  toggle: (key: "sync" | "showTr" | "sidebar") => void;
  setPage: (p: number) => void;
  setLink: (l: LinkTarget) => void;
  flashBlock: (id: string) => void;
};

export const useStore = create<State>((set, get) => ({
  data: null,
  zoom: "fit",
  scale: 1,
  sync: true,
  showTr: stored("pv.showTr", true),
  sidebar: stored("pv.sidebar", true),
  page: 1,
  link: null,
  flash: null,
  setData: (data) => set({ data, page: 1, link: null, flash: null }),
  setZoom: (zoom) => set({ zoom }),
  setScale: (scale) => get().scale !== scale && set({ scale }),
  toggle: (key) => {
    const v = !get()[key];
    if (key !== "sync") persist(`pv.${key}`, v);
    set({ [key]: v } as Partial<State>);
  },
  setPage: (page) => get().page !== page && set({ page }),
  setLink: (link) => {
    const cur = get().link;
    if (cur?.id !== link?.id || cur?.from !== link?.from) set({ link });
  },
  flashBlock: (id) => set({ flash: { id, n: (get().flash?.n ?? 0) + 1 } }),
}));
