import { DIMENSION_ORDER } from '../src/lib/reportUtils'
import type { HistoryItem } from '../src/types/history'
import type { DimensionId, ReportDimension } from '../src/types/report'

const dimensionNames: Record<DimensionId, string> = {
  programming: '程序设计',
  algorithms: '算法',
  database: '数据库',
  network: '网络',
  os: '操作系统',
  software: '软件工程',
}

export function makeDimensions(scores: Partial<Record<DimensionId, number>> = {}): ReportDimension[] {
  return DIMENSION_ORDER.map((id) => ({
    id,
    name: dimensionNames[id],
    score: scores[id] ?? 75,
    correct: 3,
    total: 4,
  }))
}

export function submittedAttempt(overrides: Partial<HistoryItem> = {}): HistoryItem {
  const id = overrides.id ?? 'attempt-submitted'
  const createdAt = overrides.createdAt ?? '2026-01-01T10:00:00Z'
  return {
    id,
    roleId: 'backend',
    roleName: '后端开发',
    status: 'submitted',
    createdAt,
    submittedAt: createdAt,
    reportId: id,
    score: 75,
    dimensions: makeDimensions(),
    modelVersion: 'scoring-v1',
    questionBankVersion: 'bank-v1',
    blueprintVersion: 'blueprint-v1',
    reusedQuestionCount: 0,
    ...overrides,
  }
}

export function inProgressAttempt(): HistoryItem {
  return submittedAttempt({
    id: 'attempt-pending',
    status: 'in_progress',
    submittedAt: null,
    reportId: null,
    score: null,
    dimensions: null,
  })
}

export function comparisonAttempts() {
  const before = submittedAttempt({
    id: 'attempt-z',
    createdAt: '2026-01-01T10:00:00Z',
    score: 72,
    dimensions: makeDimensions({ programming: 66.67, algorithms: 83.33, database: 80, network: 90, os: 55, software: 60 }),
  })
  const after = submittedAttempt({
    id: 'attempt-a',
    createdAt: '2026-01-02T10:00:00Z',
    score: 77,
    dimensions: makeDimensions({ programming: 83.33, algorithms: 66.67, database: 80, network: 70, os: 95, software: 65 }).reverse(),
  })
  return { before, after }
}
