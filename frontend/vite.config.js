import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5175,
    proxy: {
      // Document Again local backend. :8002 is QA Again's canonical port, so
      // Document Again runs on :8003 locally (P1 port-hardening fix).
      "/api": "http://localhost:8003",
    },
  },
});
