import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vite 配置：开发态把 /api 与 /ws 反向代理到后端
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.VITE_BACKEND_URL || "http://localhost:8000";
  const wsBackend = backend.replace(/^http/, "ws");
  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        "/api": { target: backend, changeOrigin: true },
        "/ws": { target: wsBackend, ws: true, changeOrigin: true },
        "/healthz": { target: backend, changeOrigin: true },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: false,
    },
  };
});
