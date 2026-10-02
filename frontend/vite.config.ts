import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8081,
    allowedHosts: ["antelligenceee.operator-jarvis.org", ".operator-jarvis.org"],
  },
  // Base URL for production - will be served from backend
  base: mode === 'production' ? '/static/' : '/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // Ensure assets work with relative paths
    rollupOptions: {
      output: {
        assetFileNames: 'assets/[name].[hash].[ext]',
        chunkFileNames: 'assets/[name].[hash].js',
        entryFileNames: 'assets/[name].[hash].js',
      }
    }
  },
  // lovable-tagger was removed: it stamped data-lov-* props onto every JSX
  // element, which React Three Fiber reads as nested paths and crashes on.
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
