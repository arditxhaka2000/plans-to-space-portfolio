import { defineConfig } from 'vite';

export default defineConfig({
  build: { outDir: '../server/wwwroot', emptyOutDir: true, rollupOptions: { input: { main: 'index.html', floors: 'floors.html', review:'review.html' },output:{entryFileNames:chunk=>chunk.name==='review'?'portal/review-[hash].js':'assets/[name]-[hash].js',chunkFileNames:chunk=>chunk.name==='three'?'portal/runtime-[hash].js':chunk.name==='modulepreload-polyfill'?'portal/[name]-[hash].js':'portal/[name]-[hash].js',manualChunks:{three:['three','three/examples/jsm/controls/OrbitControls.js']}} } },
  server: { proxy: { '/api': 'http://localhost:5088' } }
});
