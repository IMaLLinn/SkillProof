import { apiRequest } from '../api'

export type WrongStatus = 'review' | 'mastered' | 'all'
export type Practice = { id: string; selected: string[]; isCorrect: boolean; createdAt: string }
export type WrongQuestion = {
  id: string; attemptId: string; roleId: string; roleName: string
  questionId: string; dimension: string; dimensionName: string; topicId: string; topic: string
  stem: string; type: 'single' | 'multiple'; questionVersion: number; collectedAt: string
  mastered: boolean; masteryUpdatedAt: string | null; practiceCount: number
  lastPractice: { isCorrect: boolean; createdAt: string } | null
}
export type WrongDetail = WrongQuestion & {
  question: {
    id: string; stem: string; type: 'single' | 'multiple'; difficulty: string; version: number
    options: { id: string; text: string }[]; correct: string[]; explanation: string
    sources: { title: string; url: string }[]
  }
  originalAnswer: string[]
  practices: Practice[]
}
export type WrongFilter = {
  roleId: string; roleName: string; dimension: string; dimensionName: string; topicId: string; topic: string
}
export type WrongList = {
  items: WrongQuestion[]; total: number; limit: number; offset: number
  counts: Record<WrongStatus, number>; filters: WrongFilter[]
}
export type WrongQuery = { roleId: string; dimension: string; topicId: string; status: WrongStatus; offset: number }

export function fetchWrongQuestions(query: WrongQuery, signal: AbortSignal) {
  const params = new URLSearchParams({ status: query.status, limit: '20', offset: String(query.offset) })
  if (query.roleId) params.set('roleId', query.roleId)
  if (query.dimension) params.set('dimension', query.dimension)
  if (query.topicId) params.set('topicId', query.topicId)
  return apiRequest<WrongList>(`/wrong-questions?${params}`, { authenticated: true, signal })
}

export function fetchWrongDetail(id: string, signal: AbortSignal) {
  return apiRequest<WrongDetail>(`/wrong-questions/${encodeURIComponent(id)}`, { authenticated: true, signal })
}

export function saveMastery(id: string, mastered: boolean) {
  return apiRequest<WrongDetail>(`/wrong-questions/${encodeURIComponent(id)}`, {
    method: 'PATCH', authenticated: true, body: JSON.stringify({ mastered }),
  })
}

export function submitPractice(id: string, selected: string[], requestId: string) {
  return apiRequest<{ result: Practice; item: WrongDetail }>(`/wrong-questions/${encodeURIComponent(id)}/practice`, {
    method: 'POST', authenticated: true, body: JSON.stringify({ selected, requestId }),
  })
}
