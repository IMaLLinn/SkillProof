import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  try {
    cleanup()
  } finally {
    vi.unstubAllGlobals()
  }
})
