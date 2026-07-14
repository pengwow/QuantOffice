import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // 代理 FastAPI 后端（CORS 友好）
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8765',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,             // 生产构建不产 sourcemap(低内存机器减少 30%+ 内存)
    target: 'es2020',             // 降一档,减少 esbuild 转译开销
    cssCodeSplit: true,
    minify: 'esbuild',            // esbuild minify 比 terser 内存友好得多
    chunkSizeWarningLimit: 1500,
    reportCompressedSize: false, // 关闭 gzip 二次测量(默认开,会再跑一遍,1G 内存会爆)
    rollupOptions: {
      // 1H1G 机器:限制 Rollup 并发,降低峰值内存
      maxParallelFileOps: 2,
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          echarts: ['echarts', 'echarts-for-react'],
          query: ['@tanstack/react-query', 'zustand'],
        },
      },
    },
  },
}));
