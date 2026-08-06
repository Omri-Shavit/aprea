import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api -> FastAPI backend on :8000, so the frontend can
// call same-origin URLs (no CORS headaches) and you don't hardcode a host.
//
// `base` controls the public path assets are served under. Local dev uses "/".
// The GitHub Pages build sets VITE_BASE=/aprea/searchable-wee1-inhibitor-database/
// (see .github/workflows/deploy-frontend.yml).
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
