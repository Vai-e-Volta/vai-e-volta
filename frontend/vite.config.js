import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Em desenvolvimento o Vite encaminha /api e /uploads ao backend, mantendo a mesma origem
// (sem CORS). Em produção o Nginx faz esse papel (Documento Técnico, seções 11.4 e 14.4).
const backendUrl = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000';

export default defineConfig({
  base: '/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': { target: backendUrl, changeOrigin: false },
      '/uploads': { target: backendUrl, changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/**/*.test.{js,jsx}'],
    setupFiles: ['./tests/setup.js'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      reporter: ['text', 'html'],
    },
  },
});
