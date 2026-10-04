// Two routes: "/" library, "/r/:paperId?page=N" reader (deep link). History API only, no router library.
import { useEffect, useState } from "react";
import Library from "./pages/Library";
import Reader from "./pages/Reader";

export function navigate(path: string) {
  history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function App() {
  const [loc, setLoc] = useState(() => location.pathname + location.search);
  useEffect(() => {
    const on = () => setLoc(location.pathname + location.search);
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, []);
  const m = loc.match(/^\/r\/([0-9a-f]+)/);
  if (!m) return <Library />;
  const page = Number(new URLSearchParams(loc.split("?")[1] ?? "").get("page")) || 1;
  return <Reader key={m[1]} paperId={m[1]} initialPage={page} />;
}
