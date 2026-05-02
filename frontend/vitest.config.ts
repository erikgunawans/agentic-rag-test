/// <reference types="vitest/config" />
import path from 'path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Vitest config — kept separate from vite.config.ts because vite 8 + vitest
// type defs duplicate ProxyServer/Plugin types and the merged config fails
// `tsc -b`. See D-P16-06 / D-P16-07.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Co-located *.test.tsx beside the component (D-P16-07).
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
