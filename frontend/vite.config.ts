import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// The Door is code-split from the Territory (Doc 03 §7). manualChunks keeps the canvas out
// of the Door's first paint. Using import.meta.url keeps this ESM-safe (no __dirname).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          canvas: ["@xyflow/react", "dagre"],
        },
      },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
