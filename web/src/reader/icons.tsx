// Small stroke icons for the header (design.md: no decorative emoji in chrome).
const Svg = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={d} />
  </svg>
);

export const BackIcon = () => <Svg d="M15 18l-6-6 6-6" />;
export const HighlightIcon = () => <Svg d="M4 20h16M7 16l9-9 3 3-9 9H7v-3zM14 9l3 3" />;
export const ChevronDownIcon = () => <Svg d="M6 9l6 6 6-6" />;
export const CheckIcon = () => <Svg d="M5 12l5 5 9-10" />;
export const LockIcon = () => <Svg d="M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4" />;
export const UnlockIcon = () => <Svg d="M6 11h12v10H6zM8 11V7a4 4 0 0 1 7.5-2" />;
export const SidebarIcon = () => <Svg d="M4 5h16v14H4zM9 5v14" />;
export const ColumnsIcon = () => <Svg d="M4 5h16v14H4zM12 5v14" />;
