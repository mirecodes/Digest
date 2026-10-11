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
export const FolderIcon = () => <Svg d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />;
export const FileIcon = () => <Svg d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5" />;
// library status marks: prepared in the output folder, translated, highlighted, figures explained
export const PreparedIcon = () => <Svg d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 13l2 2 4-4" />;
export const TranslateIcon = () => <Svg d="M5 8l6 6M4 14l6-6 2-3M2 5h12M7 2h1M22 22l-5-10-5 10M14 18h6" />;
export const FigureIcon = () => <Svg d="M4 5h16v14H4zM4 16l5-5 4 4 2-2 5 5M15 9h.01" />;
export const LockIcon = () => <Svg d="M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4" />;
export const UnlockIcon = () => <Svg d="M6 11h12v10H6zM8 11V7a4 4 0 0 1 7.5-2" />;
export const SidebarIcon = () => <Svg d="M4 5h16v14H4zM9 5v14" />;
export const ColumnsIcon = () => <Svg d="M4 5h16v14H4zM12 5v14" />;
