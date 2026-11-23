import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Browser requests stay on the frontend origin; Vite proxies /api to FastAPI.
const target = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000';
export default defineConfig({
  plugins: [react()],
  server: { host: '0.0.0.0', proxy: { '/api': { target, changeOrigin: true } } },
});
