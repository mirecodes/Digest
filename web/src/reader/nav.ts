// Navigation actions provided by the Reader to its panes and sidebar.
import { createContext, useContext } from "react";

export type Nav = {
  goToPage: (page: number) => void;
  /** Scroll the PDF pane to a block or figure (centered) and flash it. */
  goToBlock: (id: string) => void;
  /** Scroll the translation pane to the item of a block or figure and flash it there. */
  showInTranslation: (id: string) => void;
};

const noop = () => {};
export const NavContext = createContext<Nav>({ goToPage: noop, goToBlock: noop, showInTranslation: noop });
export const useNav = () => useContext(NavContext);
