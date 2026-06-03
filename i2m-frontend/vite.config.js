import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/i2m/',
  plugins: [react(), tailwindcss()],
  server: {
    port: 8108,
    host: '0.0.0.0',
    allowedHosts: ['openhands.m2igen.com', '.m2igen.com'],
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
