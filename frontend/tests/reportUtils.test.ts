import { describe, expect, test } from 'vitest'
import { dateText, rankLabels, scoreText, selectWeakDimensions } from '../src/lib/reportUtils'
import { makeDimensions } from './historyFixtures'

const [programming, algorithms, database, network, os, software] = makeDimensions()

const weakDimensions = [
  { ...programming, correct: 0, total: 4, score: 0 },
  { ...algorithms, correct: 1, total: 4, score: 25 },
  { ...database, correct: 1, total: 2, score: 50 },
  { ...network, correct: 2, total: 4, score: 50 },
  { ...os, correct: 3, total: 6, score: 50 },
  { ...software, correct: 5001, total: 10000, score: 50.01 },
]

// 5001/10001 rounds to the same displayed score as 1/2.
const roundedTie = { ...weakDimensions[5], total: 10001, score: 50 }

describe('selectWeakDimensions', () => {
  test('includes every dimension tied at third place and excludes the next higher ratio', () => {
    const input = [...weakDimensions.slice(0, 5), roundedTie]

    expect(selectWeakDimensions(input)).toEqual(input.slice(0, 5))
  })

  test('returns the first three dimensions when there is no tie at the cutoff', () => {
    const input = [weakDimensions[0], weakDimensions[1], weakDimensions[2], weakDimensions[5]]

    expect(selectWeakDimensions(input)).toEqual(input.slice(0, 3))
  })

  test('returns the available dimensions when fewer than three are present', () => {
    const input = weakDimensions.slice(0, 2)

    expect(selectWeakDimensions(input)).toEqual(input)
    expect(selectWeakDimensions([])).toEqual([])
  })

  test('includes all six dimensions when they tie', () => {
    const input = makeDimensions()

    expect(selectWeakDimensions(input)).toEqual(input)
  })
})

describe('rankLabels', () => {
  test('shares a rank across equal ratios and skips the places those dimensions occupy', () => {
    expect(rankLabels([...weakDimensions.slice(0, 5), roundedTie])).toEqual([1, 2, 3, 3, 3, 6])
  })
})

describe('scoreText', () => {
  test('displays up to two decimal places and a placeholder for missing scores', () => {
    expect(scoreText(0)).toBe('0')
    expect(scoreText(66.67)).toBe('66.67')
    expect(scoreText(66.675)).toBe('66.68')
    expect(scoreText(90.5)).toBe('90.5')
    for (const score of [null, undefined, NaN]) {
      expect(scoreText(score)).toBe('—')
    }
  })
})

describe('dateText', () => {
  test('displays an ISO timestamp in local time to the minute', () => {
    const timestamp = new Date(2026, 0, 2, 15, 4, 59).toISOString()

    expect(dateText(timestamp)).toBe('2026/01/02 15:04')
  })

  test('displays a placeholder for absent or invalid dates', () => {
    for (const date of [null, undefined, '', 'invalid date']) {
      expect(dateText(date)).toBe('—')
    }
  })
})
