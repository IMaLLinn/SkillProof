import { fireEvent, render, screen, within } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { describe, expect, test, vi } from 'vitest'
import { ApiError } from '../src/api'
import { HistoryPage } from '../src/pages/reports/HistoryPage'
import type { HistoryItem } from '../src/types/history'
import { comparisonAttempts, inProgressAttempt, submittedAttempt } from './historyFixtures'
import { stubFetch } from './stubFetch'

type HistoryPageProps = ComponentProps<typeof HistoryPage>

function renderHistory(items: HistoryItem[], overrides: Partial<HistoryPageProps> = {}) {
  const fetchMock = stubFetch().mockResolvedValueOnce(Response.json({ items }))
  render(<HistoryPage
    onBack={vi.fn()}
    onOpenReport={vi.fn()}
    onOpenAttempt={vi.fn()}
    onRetest={vi.fn<HistoryPageProps['onRetest']>().mockResolvedValue(undefined)}
    {...overrides}
  />)
  expect(fetchMock).toHaveBeenCalledWith('/api/attempts/history', expect.any(Object))
}

async function selectBothAttempts() {
  const checkboxes = await screen.findAllByRole('checkbox', { name: '加入对比' })
  expect(checkboxes).toHaveLength(2)
  for (const checkbox of checkboxes) fireEvent.click(checkbox)
  return within(screen.getByRole('table', { name: '两次测评各维度得分与差值' }))
}

describe('HistoryPage', () => {
  test('shows the empty history state', async () => {
    renderHistory([])

    expect(await screen.findByRole('heading', { name: '还没有测评记录' })).not.toBeNull()
    expect(screen.getByRole('button', { name: '去选择岗位' })).not.toBeNull()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })

  test('compares all six dimensions when two same-role attempts are selected', async () => {
    const { before, after } = comparisonAttempts()
    renderHistory([after, before])

    const table = await selectBothAttempts()
    expect(table.getAllByRole('columnheader').map((header) => header.textContent)).toEqual(['知识维度', '基准', '对比', '差值'])
    expect(table.getAllByRole('row').slice(1).map((row) => {
      const cells = within(row)
      return [cells.getByRole('rowheader').textContent, ...cells.getAllByRole('cell').map((cell) => cell.textContent)]
    })).toEqual([
      ['程序设计', '66.67', '83.33', '+16.66'],
      ['算法', '83.33', '66.67', '-16.66'],
      ['数据库', '80', '80', '±0'],
      ['网络', '90', '70', '-20'],
      ['操作系统', '55', '95', '+40'],
      ['软件工程', '60', '65', '+5'],
    ])
  })

  test('resumes an in-progress attempt without offering comparison', async () => {
    const attempt = inProgressAttempt()
    const onOpenAttempt = vi.fn<HistoryPageProps['onOpenAttempt']>()
    renderHistory([attempt], { onOpenAttempt })

    const record = within(await screen.findByRole('article'))
    expect(record.queryByRole('checkbox')).toBeNull()
    fireEvent.click(record.getByRole('button', { name: '继续作答' }))
    expect(onOpenAttempt).toHaveBeenCalledExactlyOnceWith(attempt.id)
  })

  test('warns about a missing score snapshot and hides its report and comparison actions', async () => {
    renderHistory([submittedAttempt({ score: null, dimensions: null })])

    const record = within(await screen.findByRole('article'))
    expect(record.getByText('这次结果的分数快照不可用，无法查看详情，也不能参与对比。')).not.toBeNull()
    expect(record.queryByRole('button', { name: '查看结果' })).toBeNull()
    expect(record.queryByRole('checkbox')).toBeNull()
  })

  test('hides differences and explains mismatched scoring rules', async () => {
    const { before, after } = comparisonAttempts()
    renderHistory([{ ...after, modelVersion: 'scoring-v2' }, before])

    const table = await selectBothAttempts()
    expect(table.getAllByRole('columnheader').map((header) => header.textContent)).toEqual(['知识维度', '基准', '对比'])
    const firstRow = within(table.getAllByRole('row')[1])
    expect(firstRow.getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['66.67', '83.33'])
    expect(screen.getByText('两次测评使用的评分规则版本不同，分数不可直接相减，仅并列展示各自得分。')).not.toBeNull()
  })

  test('shows the API error message when retesting fails', async () => {
    const attempt = submittedAttempt()
    const message = '已有一场进行中的复测'
    const onRetest = vi.fn<HistoryPageProps['onRetest']>().mockRejectedValueOnce(new ApiError(409, message))
    renderHistory([attempt], { onRetest })

    fireEvent.click(await screen.findByRole('button', { name: '复测该岗位' }))

    expect((await screen.findByRole('alert')).textContent).toBe(message)
    expect(onRetest).toHaveBeenCalledExactlyOnceWith(attempt.roleId)
  })
})
