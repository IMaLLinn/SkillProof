import { describe, expect, test } from 'vitest'
import { buildComparison, deltaText, groupByRole } from '../src/lib/historyUtils'
import { comparisonAttempts, inProgressAttempt, makeDimensions, submittedAttempt } from './historyFixtures'

const limitationCases = [
  {
    title: 'disables differences when scoring rules differ',
    overrides: { modelVersion: 'scoring-v2' },
    limitation: 'scoringRule',
    diffAllowed: false,
  },
  {
    title: 'disables differences when blueprint rules differ',
    overrides: { blueprintVersion: 'blueprint-v2' },
    limitation: 'blueprintRule',
    diffAllowed: false,
  },
  {
    title: 'warns about different known question banks without disabling differences',
    overrides: { questionBankVersion: 'bank-v2' },
    limitation: 'questionBank',
    diffAllowed: true,
  },
  {
    title: 'warns about an unknown question bank instead of a version mismatch',
    overrides: { questionBankVersion: null },
    limitation: 'questionBankUnknown',
    diffAllowed: true,
  },
  {
    title: 'warns about reused questions without disabling differences',
    overrides: { reusedQuestionCount: 2 },
    limitation: 'reusedQuestions',
    diffAllowed: true,
  },
]

describe('historyUtils', () => {
  test('blocks comparing an attempt with itself', () => {
    const attempt = submittedAttempt()
    expect(buildComparison(attempt, { ...attempt })).toEqual({ ok: false, reason: 'sameAttempt' })
  })

  test('blocks attempts from different roles', () => {
    const otherRole = submittedAttempt({ id: 'attempt-frontend', roleId: 'frontend', roleName: '前端开发' })
    expect(buildComparison(submittedAttempt(), otherRole)).toEqual({ ok: false, reason: 'differentRole' })
  })

  test('blocks an in-progress attempt', () => {
    expect(buildComparison(submittedAttempt(), inProgressAttempt())).toEqual({ ok: false, reason: 'notSubmitted' })
  })

  test('blocks incomplete dimension snapshots', () => {
    const complete = submittedAttempt()
    const damaged = submittedAttempt({ id: 'attempt-damaged', score: null, dimensions: null })
    const incomplete = submittedAttempt({ id: 'attempt-incomplete', dimensions: makeDimensions().slice(0, 5) })

    expect(buildComparison(damaged, complete)).toEqual({ ok: false, reason: 'incompleteDimensions' })
    expect(buildComparison(complete, incomplete)).toEqual({ ok: false, reason: 'incompleteDimensions' })
  })

  test('orders attempts chronologically regardless of argument order', () => {
    const { before, after } = comparisonAttempts()
    const forward = buildComparison(before, after)

    expect(forward).toMatchObject({ ok: true, comparison: { before, after, limitations: [], diffAllowed: true } })
    expect(buildComparison(after, before)).toEqual(forward)
  })

  test('rounds after-minus-before deltas and formats positive negative and flat values', () => {
    const { before, after } = comparisonAttempts()
    const result = buildComparison(before, after)
    if (!result.ok) throw new Error(`Expected a comparison, received ${result.reason}`)

    expect(result.comparison.dimensions.map(({ id, delta }) => [id, delta, deltaText(delta)])).toEqual([
      ['programming', 16.66, '+16.66'],
      ['algorithms', -16.66, '-16.66'],
      ['database', 0, '±0'],
      ['network', -20, '-20'],
      ['os', 40, '+40'],
      ['software', 5, '+5'],
    ])
  })

  for (const { title, overrides, limitation, diffAllowed } of limitationCases) {
    test(title, () => {
      const { before, after } = comparisonAttempts()

      expect(buildComparison(before, { ...after, ...overrides })).toMatchObject({
        ok: true,
        comparison: { limitations: [limitation], diffAllowed },
      })
    })
  }

  test('counts only comparable records in each role', () => {
    const { before, after } = comparisonAttempts()
    const damaged = submittedAttempt({ id: 'attempt-damaged', score: null, dimensions: null })
    const pending = inProgressAttempt()
    const otherRole = submittedAttempt({ id: 'attempt-frontend', roleId: 'frontend', roleName: '前端开发' })

    expect(groupByRole([after, otherRole, pending, damaged, before])).toEqual([
      { roleId: 'backend', roleName: '后端开发', items: [after, pending, damaged, before], comparableCount: 2 },
      { roleId: 'frontend', roleName: '前端开发', items: [otherRole], comparableCount: 1 },
    ])
  })
})
