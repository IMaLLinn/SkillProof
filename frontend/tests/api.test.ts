import { afterEach, describe, expect, test, vi } from 'vitest'
import {
  ApiError, apiRequest, createAttempt, getAttempt, saveAnswers, setCsrfToken, submitAttempt,
} from '../src/api'
import type { AssessmentResult, Attempt } from '../src/pages/assessment/types'
import { makeDimensions } from './historyFixtures'
import { stubFetch } from './stubFetch'

const csrfToken = 'fixture'
const attemptId = 'attempt/1'
const attemptPath = '/api/attempts/attempt%2F1'
const singleQuestion: Attempt['questions'][number] = {
  id: 'q1',
  type: 'single',
  dimension: 'programming',
  stem: '选择正确的定义。',
  options: [{ id: 'a', text: '选项 A' }, { id: 'b', text: '选项 B' }],
}
const multipleQuestion: Attempt['questions'][number] = { ...singleQuestion, id: 'q2', type: 'multiple' }
const attempt: Attempt = {
  id: attemptId,
  roleId: 'backend',
  roleName: '后端开发',
  status: 'in_progress',
  questionCount: 2,
  answeredCount: 1,
  questions: [singleQuestion, multipleQuestion],
  answers: { q1: ['a'] },
  answersVersion: 2,
}
const result: AssessmentResult = {
  id: attempt.id,
  roleId: attempt.roleId,
  roleName: attempt.roleName,
  submittedAt: '2026-01-01T10:30:00Z',
  dimensions: makeDimensions().map(({ id, name, score }) => ({ id, name, score })),
}

function apiFailure(status: number, message: string) {
  return { name: 'ApiError', status, message }
}

const invalidAttempt = apiFailure(200, '服务器返回的测评数据不完整或格式不正确，请稍后重试')
const invalidResult = apiFailure(200, '服务器返回的提交结果格式不正确，请重试确认测评状态')

afterEach(() => {
  setCsrfToken(null)
})

describe('apiRequest', () => {
  test('sends the current CSRF token with authenticated mutations', async () => {
    setCsrfToken(csrfToken)
    const fetchMock = stubFetch().mockResolvedValueOnce(Response.json({ ok: true }))
    const body = JSON.stringify({ expectedVersion: 2 })

    await expect(apiRequest('/attempts/attempt%2F1/answers', {
      method: 'PUT', authenticated: true, body, headers: { Accept: 'application/json' },
    })).resolves.toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith(`${attemptPath}/answers`, expect.objectContaining({
      method: 'PUT', body, credentials: 'include', signal: expect.any(AbortSignal),
    }))
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers)
    expect(headers.get('X-CSRF-Token')).toBe(csrfToken)
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Accept')).toBe('application/json')
  })

  test('omits the CSRF header for read-only and unauthenticated requests', async () => {
    setCsrfToken(csrfToken)
    const fetchMock = stubFetch().mockImplementation(async () => Response.json({ ok: true }))
    await apiRequest('/catalog', { authenticated: true })
    await apiRequest('/catalog', { method: 'HEAD', authenticated: true })
    await apiRequest('/catalog', { method: 'OPTIONS', authenticated: true })
    await apiRequest('/auth/login', { method: 'POST' })

    expect(fetchMock).toHaveBeenCalledTimes(4)
    for (const [, options] of fetchMock.mock.calls) {
      expect(new Headers(options?.headers).has('X-CSRF-Token')).toBe(false)
    }
  })

  test('rejects an authenticated mutation without a token before fetching', async () => {
    const fetchMock = stubFetch()

    await expect(apiRequest('/auth/logout', { method: 'POST', authenticated: true }))
      .rejects.toMatchObject(apiFailure(403, '登录信息不完整，请刷新页面后重试'))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  test('converts HTTP errors to ApiError with status and detail', async () => {
    const fetchMock = stubFetch()
    fetchMock.mockResolvedValueOnce(Response.json({ detail: '测评不存在' }, { status: 404 }))
    fetchMock.mockResolvedValueOnce(Response.json({ detail: { message: '答案已更新' } }, { status: 409 }))

    const missing = apiRequest('/attempts/missing')
    await expect(missing).rejects.toBeInstanceOf(ApiError)
    await expect(missing).rejects.toMatchObject({ status: 404, message: '测评不存在' })
    await expect(apiRequest('/attempts/attempt%2F1')).rejects.toMatchObject({
      name: 'ApiError', status: 409, message: '答案已更新',
    })
  })

  test('uses fallback messages for malformed HTTP errors and invalid success responses', async () => {
    const fetchMock = stubFetch()
    fetchMock.mockResolvedValueOnce(new Response('Service unavailable', { status: 503 }))
    fetchMock.mockResolvedValueOnce(Response.json({ detail: { message: ' ' } }, { status: 422 }))
    fetchMock.mockResolvedValueOnce(new Response('<html></html>', { status: 200 }))

    await expect(apiRequest('/catalog')).rejects.toMatchObject(apiFailure(503, '请求失败（503），请稍后重试'))
    await expect(apiRequest('/catalog')).rejects.toMatchObject(apiFailure(422, '请求失败（422），请稍后重试'))
    await expect(apiRequest('/catalog'))
      .rejects.toMatchObject(apiFailure(200, '服务器响应格式不正确，请稍后重试'))
  })

  test('announces an authenticated 401 and clears the current CSRF token', async () => {
    setCsrfToken(csrfToken)
    const sessionExpired = vi.fn()
    const listener = new AbortController()
    window.addEventListener('session-expired', sessionExpired, { signal: listener.signal })
    const fetchMock = stubFetch().mockResolvedValueOnce(Response.json({ detail: '会话已过期' }, { status: 401 }))

    try {
      await expect(apiRequest('/auth/me', { authenticated: true }))
        .rejects.toMatchObject(apiFailure(401, '会话已过期'))
      expect(sessionExpired).toHaveBeenCalledTimes(1)
      await expect(apiRequest('/auth/logout', { method: 'POST', authenticated: true }))
        .rejects.toMatchObject(apiFailure(403, '登录信息不完整，请刷新页面后重试'))
      expect(fetchMock).toHaveBeenCalledTimes(1)
    } finally {
      listener.abort()
    }
  })

  test('distinguishes network failure, caller cancellation, and request timeout', async () => {
    const fetchMock = stubFetch()
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(apiRequest('/catalog'))
      .rejects.toMatchObject(apiFailure(0, '无法连接服务器，请检查网络后重试'))

    const cancelled = new DOMException('Cancelled', 'AbortError')
    fetchMock.mockRejectedValueOnce(cancelled)
    await expect(apiRequest('/catalog', { signal: AbortSignal.abort(cancelled) })).rejects.toBe(cancelled)

    const timedOut = new DOMException('Timed out', 'TimeoutError')
    const timeout = vi.spyOn(AbortSignal, 'timeout').mockReturnValueOnce(AbortSignal.abort(timedOut))
    try {
      fetchMock.mockRejectedValueOnce(timedOut)
      await expect(apiRequest('/catalog')).rejects.toMatchObject(apiFailure(0, '请求超时，请稍后重试'))
    } finally {
      timeout.mockRestore()
    }
  })
})

describe('assessment requests', () => {
  test('returns a valid attempt and fills in omitted answers', async () => {
    const fetchMock = stubFetch().mockResolvedValueOnce(Response.json(attempt))

    await expect(getAttempt(attemptId)).resolves.toEqual({ ...attempt, answers: { q1: ['a'], q2: [] } })
    expect(fetchMock).toHaveBeenCalledWith(attemptPath, expect.objectContaining({ credentials: 'include' }))
  })

  test('rejects malformed attempt metadata and mismatched attempt IDs', async () => {
    const fetchMock = stubFetch()
    for (const overrides of [
      { id: 'wrong-attempt' }, { id: ' ' }, { roleId: '' }, { roleName: ' ' }, { status: 'expired' },
      { answersVersion: -1 }, { answersVersion: 1.5 }, { questions: null }, { answers: null },
      { answers: 'invalid' }, { answers: [] },
    ]) {
      fetchMock.mockResolvedValueOnce(Response.json({ ...attempt, ...overrides }))
      await expect(getAttempt(attemptId), JSON.stringify(overrides)).rejects.toMatchObject(invalidAttempt)
    }
  })

  test('rejects missing, malformed, and duplicate questions or options', async () => {
    const fetchMock = stubFetch()
    for (const questions of [
      [null, multipleQuestion], [singleQuestion, singleQuestion],
      ...[
        { id: ' ' }, { dimension: ' ' }, { stem: ' ' }, { type: 'unsupported' },
        { options: null }, { options: [] }, { options: [null] },
        { options: [{ id: '', text: '选项' }] }, { options: [{ id: 'a', text: ' ' }] },
        { options: [singleQuestion.options[0], singleQuestion.options[0]] },
      ].map((overrides) => [{ ...singleQuestion, ...overrides }, multipleQuestion]),
    ]) {
      fetchMock.mockResolvedValueOnce(Response.json({ ...attempt, questions }))
      await expect(getAttempt(attemptId), JSON.stringify(questions)).rejects.toMatchObject(invalidAttempt)
    }
  })

  test('rejects answers with unknown questions or choices, duplicate choices, or invalid cardinality', async () => {
    const fetchMock = stubFetch()
    for (const answers of [{ missing: ['a'] }, { q1: 'a' }, { q1: ['a', 'b'] },
      { q2: [1] }, { q2: ['unknown'] }, { q2: ['a', 'a'] }]) {
      fetchMock.mockResolvedValueOnce(Response.json({ ...attempt, answers }))
      await expect(getAttempt(attemptId), JSON.stringify(answers)).rejects.toMatchObject(invalidAttempt)
    }
  })

  test('rejects inconsistent question and answer counts', async () => {
    const fetchMock = stubFetch()
    for (const overrides of [{ questionCount: 3 }, { answers: { q1: ['a'], q2: [] }, answeredCount: 2 }]) {
      fetchMock.mockResolvedValueOnce(Response.json({ ...attempt, ...overrides }))
      await expect(getAttempt(attemptId), JSON.stringify(overrides)).rejects.toMatchObject(invalidAttempt)
    }
  })

  test('rejects a created attempt for a different role', async () => {
    setCsrfToken(csrfToken)
    stubFetch().mockResolvedValueOnce(Response.json(attempt))

    await expect(createAttempt('frontend')).rejects.toMatchObject(apiFailure(200, '服务器返回的测评岗位不一致，请重试'))
  })

  test('saves multiple-choice answers with the expected version and validates the response', async () => {
    setCsrfToken(csrfToken)
    const answers = { q1: [], q2: ['a', 'b'] }
    const saved = { ...attempt, answers, answersVersion: 3 }
    const fetchMock = stubFetch()
    fetchMock.mockResolvedValueOnce(Response.json(saved))
    fetchMock.mockResolvedValueOnce(Response.json({ ...saved, id: 'wrong-attempt' }))

    await expect(saveAnswers(attemptId, answers, 2)).resolves.toEqual(saved)
    expect(fetchMock).toHaveBeenCalledWith(`${attemptPath}/answers`, expect.objectContaining({
      method: 'PUT', body: JSON.stringify({ answers, expectedVersion: 2 }),
    }))
    await expect(saveAnswers(attemptId, answers, 2)).rejects.toMatchObject(invalidAttempt)
  })

  test('accepts a submitted result with all six valid dimensions', async () => {
    setCsrfToken(csrfToken)
    const fetchMock = stubFetch().mockResolvedValueOnce(Response.json(result))

    await expect(submitAttempt(attemptId)).resolves.toEqual(result)
    expect(fetchMock).toHaveBeenCalledWith(`${attemptPath}/submit`, expect.objectContaining({ method: 'POST' }))
  })

  test('rejects submitted results with invalid IDs, timestamps, or dimensions', async () => {
    setCsrfToken(csrfToken)
    const fetchMock = stubFetch()
    const [first, ...remaining] = result.dimensions
    for (const overrides of [
      { id: 'wrong-attempt' }, { roleId: '' }, { roleName: ' ' },
      { submittedAt: '' }, { submittedAt: 'not a date' },
      { dimensions: null }, { dimensions: remaining },
      ...[null, remaining[0], { ...first, id: 'other' }, { ...first, name: ' ' },
        { ...first, score: '75' }, { ...first, score: -1 }, { ...first, score: 101 },
      ].map((dimension) => ({ dimensions: [dimension, ...remaining] })),
    ]) {
      fetchMock.mockResolvedValueOnce(Response.json({ ...result, ...overrides }))
      await expect(submitAttempt(attemptId), JSON.stringify(overrides)).rejects.toMatchObject(invalidResult)
    }
  })
})
