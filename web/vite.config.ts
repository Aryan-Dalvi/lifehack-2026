import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Four people and several AI windows run this repo at once, so a second stack has to be
// able to come up beside a first one rather than fighting it for a port.
// Declared rather than pulled in from @types/node: this is the only Node global the config
// touches, and the app itself has no Node types and does not need them.
declare const process: { env: Record<string, string | undefined> };

const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
const webPort = Number(process.env.WEB_PORT ?? 5173);

export default defineConfig({
  plugins: [react()],
  server: {
    port: webPort,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});

