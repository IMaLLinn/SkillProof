import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { setCsrfToken } from '../src/api'
import type { WrongDetail, WrongList } from '../src/lib/wrongbookApi'
import { WrongbookPage } from '../src/pages/reports/WrongbookPage'
import { stubFetch } from './stubFetch'

function wrongDetail(): WrongDetail {
  return {
    id: 'wrong-one', attemptId: 'attempt-one', roleId: 'backend', roleName: '后端开发',
    questionId: 'q-one', dimension: 'database', dimensionName: '数据库', topicId: 'database.transaction',
    topic: '事务原子性', stem: '事务失败时应该如何处理已执行的更新？', type: 'multiple',
    questionVersion: 2, collectedAt: '2026-11-27T03:00:00Z', mastered: false,
    masteryUpdatedAt: null, practiceCount: 0, lastPractice: null, originalAnswer: ['A'], practices: [],
    question: { id: 'q-one', stem: '事务失败时应该如何处理已执行的更新？', type: 'multiple',
      difficulty: 'medium', version: 2, options: [
        { id: 'A', text: '仅保留已经成功的更新' }, { id: 'B', text: '回滚本次事务' }, { id: 'C', text: '保留之前已经提交的数据' },
      ], correct: ['B', 'C'], explanation: '事务内的更新要么一起成功，要么一起回滚。', sources: [],
    },
  }
}

function listOf(item: WrongDetail, include = true): WrongList {
  return { items: include ? [item] : [], total: include ? 1 : 0, limit: 20, offset: 0,
    counts: { all: 1, review: item.mastered ? 0 : 1, mastered: item.mastered ? 1 : 0 },
    filters: [{ roleId: item.roleId, roleName: item.roleName, dimension: item.dimension,
      dimensionName: item.dimensionName, topicId: item.topicId, topic: item.topic }],
  }
}

function renderPage() {
  return render(<WrongbookPage onBack={vi.fn()} onOpenReport={vi.fn()} />)
}

async function selectFirstQuestion() {
  fireEvent.click(await screen.findByRole('button', { name: /事务失败时应该如何处理/ }))
  await screen.findByRole('heading', { name: '事务失败时应该如何处理已执行的更新？' })
}

describe('WrongbookPage', () => {
  test('shows a genuine empty state without an invented question', async () => {
    const empty = { ...listOf(wrongDetail(), false), counts: { all: 0, review: 0, mastered: 0 }, filters: [] }
    stubFetch().mockResolvedValue(Response.json(empty))
    renderPage()
    expect(await screen.findByRole('heading', { name: '还没有收集到错题' })).not.toBeNull()
    expect(screen.queryByRole('button', { name: '重练这道题' })).toBeNull()
  })

  test('hides the solution while practicing, persists a result and keeps mastery manual', async () => {
    const item = wrongDetail()
    const result = { id: 'practice-one', selected: ['B', 'C'], isCorrect: true, createdAt: '2026-11-27T04:00:00Z' }
    const updated = { ...item, practiceCount: 1, practices: [result], lastPractice: result }
    const fetchMock = stubFetch().mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/practice')) return Response.json({ result, item: updated })
      if (url.includes('?')) return Response.json(listOf(item))
      return Response.json(item)
    })
    setCsrfToken('test-csrf-token')
    renderPage()
    await selectFirstQuestion()
    expect(screen.getByText('正确答案')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '重练这道题' }))
    expect(screen.queryByText('正确答案')).toBeNull()
    const submit = screen.getByRole('button', { name: '提交重练答案' })
    expect((submit as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('checkbox', { name: /回滚本次事务/ }))
    fireEvent.click(screen.getByRole('checkbox', { name: /保留之前已经提交的数据/ }))
    fireEvent.click(submit)
    expect(await screen.findByText(/本次重练回答正确/)).not.toBeNull()
    expect(screen.getByRole('button', { name: '标记为已掌握' })).not.toBeNull()
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/practice'))
    const body = JSON.parse(String(call?.[1]?.body))
    expect(body.selected).toEqual(['B', 'C'])
    expect(body.requestId).toMatch(/^[0-9a-f-]{36}$/)
    expect(call?.[1]?.headers).toBeInstanceOf(Headers)
    expect((call?.[1]?.headers as Headers).get('X-CSRF-Token')).toBe('test-csrf-token')
  })

  test('moves an item to mastered and back through the API', async () => {
    let item = wrongDetail()
    stubFetch().mockImplementation(async (input, init) => {
      if (init?.method === 'PATCH') {
        item = { ...item, mastered: JSON.parse(String(init.body)).mastered }
        return Response.json(item)
      }
      if (String(input).includes('?')) return Response.json(listOf(item, !item.mastered))
      return Response.json(item)
    })
    setCsrfToken('test-csrf-token')
    renderPage()
    await selectFirstQuestion()
    fireEvent.click(screen.getByRole('button', { name: '标记为已掌握' }))
    expect(await screen.findByRole('button', { name: '移回待复习' })).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '移回待复习' }))
    expect(await screen.findByRole('button', { name: '标记为已掌握' })).not.toBeNull()
  })

  test('sends role, dimension and topic filters and clears the old detail', async () => {
    const item = wrongDetail()
    const fetchMock = stubFetch().mockImplementation(async (input) => Response.json(String(input).includes('?') ? listOf(item) : item))
    renderPage()
    await selectFirstQuestion()
    fireEvent.change(screen.getByRole('combobox', { name: '岗位' }), { target: { value: 'backend' } })
    fireEvent.change(screen.getByRole('combobox', { name: '能力维度' }), { target: { value: 'database' } })
    fireEvent.change(screen.getByRole('combobox', { name: '知识点' }), { target: { value: 'database.transaction' } })
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('roleId=backend&dimension=database&topicId=database.transaction'))).toBe(true))
    expect(screen.queryByRole('button', { name: '重练这道题' })).toBeNull()
  })

  test('shows a load error and allows a successful retry', async () => {
    const fetchMock = stubFetch().mockRejectedValueOnce(new TypeError('network error')).mockResolvedValue(Response.json(listOf(wrongDetail())))
    renderPage()
    expect(await screen.findByRole('alert')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }))
    expect(await screen.findByRole('button', { name: /事务失败时应该如何处理/ })).not.toBeNull()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  test('keeps the original review and allows retry after a practice save fails', async () => {
    const item = wrongDetail()
    stubFetch().mockImplementation(async (input) => {
      if (String(input).endsWith('/practice')) return Response.json({ detail: '练习保存失败' }, { status: 503 })
      return Response.json(String(input).includes('?') ? listOf(item) : item)
    })
    setCsrfToken('test-csrf-token')
    renderPage()
    await selectFirstQuestion()
    fireEvent.click(screen.getByRole('button', { name: '重练这道题' }))
    fireEvent.click(screen.getByRole('checkbox', { name: /回滚本次事务/ }))
    fireEvent.click(screen.getByRole('button', { name: '提交重练答案' }))
    expect((await screen.findByRole('alert')).textContent).toContain('练习保存失败')
    expect((screen.getByRole('checkbox', { name: /回滚本次事务/ }) as HTMLInputElement).checked).toBe(true)
    expect((screen.getByRole('button', { name: '提交重练答案' }) as HTMLButtonElement).disabled).toBe(false)
  })
})
