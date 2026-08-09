import path from "node:path";
import process from "node:process";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API_PROXY = process.env.VITE_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: {
    rollupOptions: {
      output: {
        // recharts is by far the heaviest dependency and is only used on the dashboard.
        // Splitting it keeps the login/onboarding entry small on a phone connection.
        manualChunks: {
          charts: ["recharts"],
          vendor: ["react", "react-dom", "react-router-dom", "@tanstack/react-query"],
        },
      },
    },
  },
  server: {
    port: 5173,
    // The SPA talks to /api and /files on the same origin in dev, so no CORS dance
    // and no environment-specific base URL in the client code. Inside Docker the API is
    // reachable as `api`, not localhost — hence the override.
    proxy: {
      "/api": { target: API_PROXY, changeOrigin: true },
      "/files": { target: API_PROXY, changeOrigin: true },
    },
  },
});
