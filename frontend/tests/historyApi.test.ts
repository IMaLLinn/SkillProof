import { describe, expect, test } from 'vitest'
import { fetchHistory } from '../src/lib/historyApi'
import { inProgressAttempt, makeDimensions, submittedAttempt } from './historyFixtures'
import { stubFetch } from './stubFetch'

const invalidPayloads = [
  {
    title: 'rejects an in-progress attempt with a score',
    items: [{ ...inProgressAttempt(), score: 75 }],
  },
  {
    title: 'rejects a submitted attempt without a report ID',
    items: [{ ...submittedAttempt(), reportId: undefined }],
  },
  {
    title: 'rejects a snapshot with only five dimensions',
    items: [submittedAttempt({ dimensions: makeDimensions().slice(0, 5) })],
  },
  {
    title: 'rejects duplicate attempt IDs',
    items: [submittedAttempt(), submittedAttempt()],
  },
]

describe('fetchHistory', () => {
  test('returns valid history from the authenticated endpoint', async () => {
    const items = [submittedAttempt(), inProgressAttempt()]
    const fetchMock = stubFetch().mockResolvedValueOnce(Response.json({ items }))

    await expect(fetchHistory()).resolves.toEqual({ ok: true, items })
    expect(fetchMock).toHaveBeenCalledWith('/api/attempts/history', expect.objectContaining({ credentials: 'include' }))
  })

  for (const { title, items } of invalidPayloads) {
    test(title, async () => {
      stubFetch().mockResolvedValueOnce(Response.json({ items }))

      await expect(fetchHistory()).resolves.toEqual({
        ok: false,
        error: { kind: 'server', status: null, message: '历史记录数据格式不正确，请稍后重试。' },
      })
    })
  }

  test('maps 401 to unauthorized and announces the expired session', async () => {
    stubFetch().mockResolvedValueOnce(Response.json({ detail: 'Session expired' }, { status: 401 }))
    const controller = new AbortController()
    let sessionExpiredCount = 0
    window.addEventListener('session-expired', () => { sessionExpiredCount += 1 }, { signal: controller.signal })

    try {
      await expect(fetchHistory()).resolves.toEqual({
        ok: false,
        error: { kind: 'unauthorized', status: 401, message: '登录状态已失效，请重新登录后再查看历史记录。' },
      })
      expect(sessionExpiredCount).toBe(1)
    } finally {
      controller.abort()
    }
  })

  test('maps a rejected fetch to a network error', async () => {
    stubFetch().mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await expect(fetchHistory()).resolves.toEqual({
      ok: false,
      error: { kind: 'network', status: 0, message: '网络连接失败，请检查网络后重试。' },
    })
  })
})
