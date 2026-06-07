import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    // Pure transform/classifier units — no DOM needed, so the fast `node`
    // environment is enough. `src/test/setup.js` is reserved for future
    // component (jsdom) tests.
    environment: 'node',
    include: ['src/**/*.test.{js,jsx}'],
    coverage: {
      provider: 'v8',
      // Scope to the pure-logic modules under test. clinicalApi.js / supabase.js
      // are side-effecting integration modules (the next test tiers) — including
      // them would dilute the metric with code these unit tests never exercise.
      include: ['src/lib/clinicalMappers.js', 'src/lib/helpers.js', 'src/lib/safetyClassify.js'],
      reporter: ['text', 'json-summary'],
    },
  },
})
