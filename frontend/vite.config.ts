import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5173 (the backend allow-lists this origin for CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/v1": "http://localhost:8000",
    },
  },
});
