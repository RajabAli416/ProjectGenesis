import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  css: {
    modules: {
      localsConvention: 'camelCaseOnly',
      generateScopedName: '[name]__[local]__[hash:base64:4]',
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      // Forwarded to the FastAPI backend during development once it exists.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
  build: {
    target: 'es2022',
    sourcemap: false,
    // pixi.js is a single ~500 kB chunk loaded only by the Universe route.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/pixi.js') || id.includes('node_modules/@pixi/')) return 'pixi';
          if (/node_modules\/(react|react-dom|react-router|scheduler)\//.test(id.replace(/\\/g, '/'))) return 'react';
          return undefined;
        },
      },
    },
  },
});
