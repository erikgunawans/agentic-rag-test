// Vitest setup — runs once before each test file.
// Adds @testing-library/jest-dom matchers (toBeInTheDocument, etc.) and
// ensures cleanup between tests.
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})
