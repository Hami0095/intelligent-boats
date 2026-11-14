import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/test/research-live.e2e.tsx"],
    testTimeout: 30000,
    hookTimeout: 15000,
  },
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
});
