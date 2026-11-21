import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { LearningRecommendations } from '../src/components/reports/LearningRecommendations'
import type { Recommendation } from '../src/lib/reportApi'
import { stubFetch } from './stubFetch'

const attemptId = 'attempt-recommendations'
const recommendations: Recommendation[] = [
  {
    id: 'programming',
    name: '程序设计',
    description: '复习控制流与函数。',
    resources: [{
      topicId: 'functions',
      topic: '函数',
      title: '函数基础',
      summary: '通过参数和返回值组织代码。',
      source: 'MDN',
      url: 'https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Guide/Functions',
      exercise: '写一个求和函数。\n用两个例子验证返回值。',
      expectedResult: '返回两个参数的和。',
    }],
  },
  {
    id: 'database',
    name: '数据库',
    description: '复习关系型数据库查询。',
    resources: [{
      topicId: 'joins',
      topic: '连接查询',
      title: '表连接教程',
      summary: '按共同字段组合两张表的数据。',
      source: 'PostgreSQL',
      url: 'https://www.postgresql.org/docs/current/tutorial-join.html',
      exercise: '编写查询，连接两张表。',
      expectedResult: '只输出满足连接条件的行。',
    }],
  },
]

describe('LearningRecommendations', () => {
  test('renders group headings and resource links that open in new tabs', async () => {
    const fetchMock = stubFetch().mockResolvedValueOnce(Response.json({ items: recommendations }))
    render(<LearningRecommendations attemptId={attemptId} />)

    for (const group of recommendations) {
      expect(await screen.findByRole('heading', { level: 3, name: group.name })).not.toBeNull()
      for (const resource of group.resources) {
        expect(screen.getByRole('heading', { level: 4, name: resource.title })).not.toBeNull()
        const link = screen.getByRole('link', { name: new RegExp(`^打开资料.*${resource.topic}`) })
        expect(link.getAttribute('href')).toBe(resource.url)
        expect(link.getAttribute('target')).toBe('_blank')
      }
    }
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/reports\/attempt-recommendations\/recommendations$/),
      expect.any(Object),
    )
  })

  test('shows the empty message when there are no recommendations', async () => {
    stubFetch().mockResolvedValueOnce(Response.json({ items: [] }))
    render(<LearningRecommendations attemptId={attemptId} />)

    expect(await screen.findByText('本次暂无学习建议。')).not.toBeNull()
    expect(screen.queryByRole('link', { name: /^打开资料/ })).toBeNull()
  })

  test('shows a load error and renders resources after a successful retry', async () => {
    const fetchMock = stubFetch().mockResolvedValueOnce(Response.json({ detail: 'Unavailable' }, { status: 503 }))
    render(<LearningRecommendations attemptId={attemptId} />)

    expect(await screen.findByText('暂时无法加载学习建议。')).not.toBeNull()
    fetchMock.mockResolvedValueOnce(Response.json({ items: recommendations }))
    fireEvent.click(screen.getByRole('button', { name: '重试' }))

    expect(await screen.findByRole('heading', { name: '函数基础' })).not.toBeNull()
    expect(screen.getAllByRole('link', { name: /^打开资料/ })).toHaveLength(2)
    expect(screen.queryByText('暂时无法加载学习建议。')).toBeNull()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  test('rejects a payload containing a non-HTTPS resource URL', async () => {
    const [first, second] = recommendations
    const unsafeGroup: Recommendation = {
      ...second,
      resources: second.resources.map((resource) => ({ ...resource, url: 'http://example.org/tutorial' })),
    }
    stubFetch().mockResolvedValueOnce(Response.json({ items: [first, unsafeGroup] }))
    render(<LearningRecommendations attemptId={attemptId} />)

    expect(await screen.findByText('暂时无法加载学习建议。')).not.toBeNull()
    expect(screen.queryByRole('link', { name: /^打开资料/ })).toBeNull()
  })
})
