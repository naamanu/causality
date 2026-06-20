import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5173 (the backend allow-lists this origin for CORS).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
