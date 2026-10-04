import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies the API and the pdf.js data files (fonts, cmaps, wasm) to the FastAPI server.
const api = `http://127.0.0.1:${process.env.VIEWER_API_PORT ?? "8765"}`;

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": api, "/pdfjs": api } },
  build: { chunkSizeWarningLimit: 1500 }, // local app: pdf.js dominates the bundle, splitting buys nothing
  test: { include: ["tests/unit/**/*.test.ts"] },
});
