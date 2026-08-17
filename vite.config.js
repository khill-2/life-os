import { readFileSync } from 'fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'inline-dashboard',
      transformIndexHtml() {
        const data = readFileSync('./public/data/dashboard.json', 'utf-8')
        return [{
          tag: 'script',
          attrs: { type: 'text/javascript' },
          children: `window.__DASHBOARD_DATA__ = ${data};`,
          injectTo: 'head-prepend',
        }]
      },
    },
  ],
})
