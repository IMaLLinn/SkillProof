import { describe, expect, test } from 'vitest'
import { fetchRecommendations, fetchReport } from '../src/lib/reportApi'
import type { Recommendation } from '../src/lib/reportApi'
import type { Report } from '../src/types/report'
import { makeDimensions } from './historyFixtures'
import { stubFetch } from './stubFetch'

const attemptId = 'attempt/report #1'
const reportPath = /\/api\/reports\/attempt%2Freport%20%231$/
const recommendationsPath = /\/api\/reports\/attempt%2Freport%20%231\/recommendations$/
const [programming, algorithms, database, network, os, software] = makeDimensions()
const weakest = { ...database, score: 25, correct: 1 }
const perfect = { ...software, score: 100, correct: 4 }
const report: Report = {
  id: attemptId,
  roleId: 'backend',
  roleName: '后端开发',
  createdAt: '2026-01-01T10:00:00Z',
  submittedAt: '2026-01-01T10:30:00Z',
  modelVersion: 'scoring-v1',
  score: 71.25,
  correctCount: 17,
  questionCount: 24,
  dimensions: [programming, algorithms, weakest, network, os, perfect],
  weakDimensions: [weakest, programming, algorithms, network, os],
}

const resource: Recommendation['resources'][number] = {
  topicId: 'joins',
  topic: '连接查询',
  title: '表连接教程',
  summary: '按共同字段组合两张表的数据。',
  source: 'PostgreSQL',
  url: 'https://www.postgresql.org/docs/current/tutorial-join.html',
  exercise: '编写查询，连接两张表。',
  expectedResult: '只输出满足连接条件的行。',
}
const recommendation: Recommendation = {
  id: 'database',
  name: '数据库',
  description: '复习关系型数据库查询。',
  resources: [resource],
}

const malformedReportCases = [
  {
    title: 'rejects reports with invalid snapshot fields and scores',
    examples: [
      ['null report', null],
      ['missing ID', { ...report, id: undefined }],
      ['blank role ID', { ...report, roleId: ' ' }],
      ['missing role name', { ...report, roleName: undefined }],
      ['missing creation date', { ...report, createdAt: null }],
      ['missing submission date', { ...report, submittedAt: undefined }],
      ['missing model version', { ...report, modelVersion: undefined }],
      ['string score', { ...report, score: '71.25' }],
      ['negative score', { ...report, score: -1 }],
      ['score over 100', { ...report, score: 101 }],
    ],
  },
  {
    title: 'rejects incomplete, duplicated, unknown, or malformed dimensions',
    examples: [
      ['missing dimensions', { ...report, dimensions: null }],
      ['five dimensions', { ...report, dimensions: report.dimensions.slice(0, 5) }],
      ['duplicate ID', { ...report, dimensions: [programming, ...report.dimensions.slice(0, 5)] }],
      ...[
        ['unknown ID', { ...perfect, id: 'other' }],
        ['blank ID', { ...perfect, id: '' }],
        ['blank name', { ...perfect, name: ' ' }],
        ['invalid score', { ...perfect, score: 101 }],
        ['fractional correct count', { ...perfect, correct: 3.5 }],
        ['negative question count', { ...perfect, total: -1 }],
        ['zero questions', { ...perfect, total: 0 }],
        ['more correct answers than questions', { ...perfect, correct: 5 }],
        ['null dimension', null],
      ].map(([label, dimension]) => [label, { ...report, dimensions: [...report.dimensions.slice(0, 5), dimension] }]),
    ],
  },
  {
    title: 'rejects invalid report counts and mismatches with dimension totals',
    examples: [
      ['non-numeric correct count', { ...report, correctCount: '17' }],
      ['fractional question count', { ...report, questionCount: 24.5 }],
      ['zero questions', { ...report, correctCount: 0, questionCount: 0 }],
      ['correct count exceeds question count', { ...report, correctCount: 25 }],
      ['question total differs', { ...report, questionCount: 25 }],
      ['correct total differs', { ...report, correctCount: 18 }],
    ],
  },
  {
    title: 'rejects weak dimensions with missing IDs, extra IDs, or mismatched values',
    examples: [
      ['missing list', { ...report, weakDimensions: null }],
      ['malformed item', { ...report, weakDimensions: [null] }],
      ['missing weak item', { ...report, weakDimensions: report.weakDimensions.slice(1) }],
      ['duplicate weak item', { ...report, weakDimensions: [programming, ...report.weakDimensions.slice(1)] }],
      ['perfect item included', { ...report, weakDimensions: [...report.weakDimensions, perfect] }],
      ['wrong weak ID', { ...report, weakDimensions: [perfect, ...report.weakDimensions.slice(1)] }],
      ...[
        ['different score', { ...weakest, score: 26 }],
        ['different correct count', { ...weakest, correct: 2 }],
        ['different question count', { ...weakest, total: 8 }],
      ].map(([label, weak]) => [label, { ...report, weakDimensions: [weak, ...report.weakDimensions.slice(1)] }]),
    ],
  },
  {
    title: 'rejects weak dimensions out of ratio order or out of order within a tie',
    examples: [
      ['ratios in descending order', { ...report, weakDimensions: [programming, weakest, algorithms, network, os] }],
      ['tie in the wrong dimension order', { ...report, weakDimensions: [weakest, algorithms, programming, network, os] }],
    ],
  },
]

const invalidReportResult = {
  ok: false,
  error: { kind: 'server', status: 200, message: '报告数据格式不正确，请稍后重试。' },
}

describe('fetchReport', () => {
  test('returns a valid snapshot unchanged from the authenticated endpoint', async () => {
    const fetchMock = stubFetch().mockResolvedValueOnce(Response.json(report))
    const { signal } = new AbortController()

    await expect(fetchReport(attemptId, signal)).resolves.toEqual({ ok: true, report })
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(reportPath), {
      method: 'GET', credentials: 'include', headers: { Accept: 'application/json' }, signal,
    })
  })

  for (const { title, examples } of malformedReportCases) {
    test(title, async () => {
      const fetchMock = stubFetch()
      for (const [label, payload] of examples) {
        fetchMock.mockResolvedValueOnce(Response.json(payload))
        await expect(fetchReport(attemptId), String(label)).resolves.toEqual(invalidReportResult)
      }
    })
  }

  test('maps 401 to unauthorized and uses the default login message', async () => {
    stubFetch().mockResolvedValueOnce(Response.json({ detail: ' ' }, { status: 401 }))

    await expect(fetchReport(attemptId)).resolves.toEqual({
      ok: false,
      error: { kind: 'unauthorized', status: 401, message: '登录状态已失效，请重新登录后再查看测评报告。' },
    })
  })

  test('maps 404 to not found and preserves the server detail', async () => {
    stubFetch().mockResolvedValueOnce(Response.json({ detail: { message: '报告不存在' } }, { status: 404 }))

    await expect(fetchReport(attemptId)).resolves.toEqual({
      ok: false,
      error: { kind: 'notFound', status: 404, message: '报告不存在' },
    })
  })

  test('distinguishes forbidden, unsubmitted, and server errors', async () => {
    const fetchMock = stubFetch()
    fetchMock.mockResolvedValueOnce(Response.json({ detail: '无权查看' }, { status: 403 }))
    fetchMock.mockResolvedValueOnce(Response.json({ detail: { message: '' } }, { status: 409 }))
    fetchMock.mockResolvedValueOnce(new Response('Bad Gateway', { status: 502 }))

    await expect(fetchReport(attemptId)).resolves.toEqual({
      ok: false, error: { kind: 'forbidden', status: 403, message: '无权查看' },
    })
    await expect(fetchReport(attemptId)).resolves.toEqual({
      ok: false, error: { kind: 'conflict', status: 409, message: '这次测评尚未提交，暂时没有可查看的结果。' },
    })
    await expect(fetchReport(attemptId)).resolves.toEqual({
      ok: false, error: { kind: 'server', status: 502, message: '报告加载失败，请稍后重试。' },
    })
  })

  test('maps a fetch failure to a network error with no HTTP status', async () => {
    stubFetch().mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await expect(fetchReport(attemptId)).resolves.toEqual({
      ok: false,
      error: { kind: 'network', status: null, message: '网络连接失败，请检查网络后重试。' },
    })
  })

  test('propagates request cancellation', async () => {
    const error = new DOMException('Cancelled', 'AbortError')
    stubFetch().mockRejectedValueOnce(error)

    await expect(fetchReport(attemptId)).rejects.toBe(error)
  })
})

describe('fetchRecommendations', () => {
  test('returns valid items with HTTPS resources', async () => {
    const items = [recommendation]
    const fetchMock = stubFetch().mockResolvedValueOnce(Response.json({ items }))
    const { signal } = new AbortController()

    await expect(fetchRecommendations(attemptId, signal)).resolves.toEqual(items)
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(recommendationsPath), {
      credentials: 'include', headers: { Accept: 'application/json' }, signal,
    })
  })

  test('accepts an empty item list', async () => {
    stubFetch().mockResolvedValueOnce(Response.json({ items: [] }))

    await expect(fetchRecommendations(attemptId, new AbortController().signal)).resolves.toEqual([])
  })

  test('rejects malformed item lists, groups, and resources', async () => {
    const fetchMock = stubFetch()
    const { signal } = new AbortController()
    for (const payload of [
      'invalid payload', null, {}, { items: {} }, { items: [null] },
      { items: [{ ...recommendation, description: ' ' }] },
      { items: [{ ...recommendation, resources: {} }] },
      { items: [{ ...recommendation, resources: [resource, { ...resource, expectedResult: undefined }] }] },
      { items: [{ ...recommendation, resources: [{ ...resource, topic: 1 }] }] },
    ]) {
      fetchMock.mockResolvedValueOnce(Response.json(payload))
      await expect(fetchRecommendations(attemptId, signal)).rejects.toThrow('Invalid learning recommendations')
    }
  })

  test('rejects the entire payload when a resource uses HTTP', async () => {
    const insecureResource = { ...resource, url: 'http://example.org/tutorial' }
    stubFetch().mockResolvedValueOnce(Response.json({
      items: [recommendation, { ...recommendation, resources: [insecureResource] }],
    }))

    await expect(fetchRecommendations(attemptId, new AbortController().signal))
      .rejects.toThrow('Invalid learning recommendations')
  })

  test('rejects a failed learning recommendations response', async () => {
    stubFetch().mockResolvedValueOnce(Response.json({ detail: 'Unavailable' }, { status: 503 }))

    await expect(fetchRecommendations(attemptId, new AbortController().signal))
      .rejects.toThrow('Could not load learning recommendations')
  })
})
