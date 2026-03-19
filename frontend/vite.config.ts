import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// The FastAPI backend runs on port 8000 by default.
// During development, Vite proxies /api/* requests to the backend.
// In production, deploy the built dist/ folder behind the same
// origin as the FastAPI server (e.g. serve via nginx or uvicorn StaticFiles).

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  root: ".",
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    proxy: {
      // Proxy all /api calls to FastAPI backend
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
