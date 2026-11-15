import { ApiError, apiRequest } from '../api'
import { DIMENSION_ORDER } from './reportUtils'
import type { HistoryItem } from '../types/history'
import type { ReportDimension } from '../types/report'

export type HistoryErrorKind = 'unauthorized' | 'network' | 'server'

export interface HistoryLoadError {
  kind: HistoryErrorKind
  status: number | null
  message: string
}

export type HistoryLoadResult =
  | { ok: true; items: HistoryItem[] }
  | { ok: false; error: HistoryLoadError }

const DEFAULT_MESSAGE: Record<HistoryErrorKind, string> = {
  unauthorized: '登录状态已失效，请重新登录后再查看历史记录。',
  network: '网络连接失败，请检查网络后重试。',
  server: '历史记录加载失败，请稍后重试。',
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isScore(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function isDimension(value: unknown): value is ReportDimension {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  if (!isNonEmptyString(item.id) || !isNonEmptyString(item.name)) return false
  if (!isScore(item.score)) return false
  if (!isCount(item.correct) || !isCount(item.total) || item.total === 0) return false
  return (item.correct as number) <= (item.total as number)
}

/** 六维摘要要么为 null，要么必须恰好包含六个固定维度且互不重复。 */
function isCompleteDimensions(value: unknown): value is ReportDimension[] {
  if (!Array.isArray(value) || value.length !== DIMENSION_ORDER.length) return false
  if (!value.every(isDimension)) return false
  const ids = value.map((item) => (item as ReportDimension).id)
  return new Set(ids).size === ids.length && DIMENSION_ORDER.every((id) => ids.includes(id))
}

/**
 * 校验单条历史记录。
 * 只接受契约允许的字段组合：进行中不得带报告 ID 与分数，
 * 已提交必须带报告 ID，且六维摘要存在时必须完整。
 */
function isHistoryItem(value: unknown): value is HistoryItem {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>

  if (!isNonEmptyString(item.id)) return false
  if (!isNonEmptyString(item.roleId) || !isNonEmptyString(item.roleName)) return false
  if (item.status !== 'in_progress' && item.status !== 'submitted') return false
  if (!isNonEmptyString(item.createdAt)) return false
  if (!isNonEmptyString(item.modelVersion) || !isNonEmptyString(item.blueprintVersion)) return false
  if (!isCount(item.reusedQuestionCount)) return false
  if (item.questionBankVersion !== null && !isNonEmptyString(item.questionBankVersion)) return false

  if (item.score !== null && !isScore(item.score)) return false
  if (item.dimensions !== null && !isCompleteDimensions(item.dimensions)) return false

  if (item.status === 'in_progress') {
    return item.reportId === null && item.submittedAt === null && item.score === null
  }
  if (!isNonEmptyString(item.reportId) || !isNonEmptyString(item.submittedAt)) return false
  return true
}

function isHistoryPayload(value: unknown): value is { items: HistoryItem[] } {
  if (typeof value !== 'object' || value === null) return false
  const { items } = value as { items?: unknown }
  if (!Array.isArray(items) || !items.every(isHistoryItem)) return false
  const ids = items.map((item) => (item as HistoryItem).id)
  return new Set(ids).size === ids.length
}

function toError(kind: HistoryErrorKind, status: number | null, detail: string | null): HistoryLoadError {
  return { kind, status, message: detail ?? DEFAULT_MESSAGE[kind] }
}

/** 读取本人全部历史测评记录；不传筛选参数，筛选在页面内完成，避免重复请求。 */
export async function fetchHistory(signal?: AbortSignal): Promise<HistoryLoadResult> {
  let payload: unknown
  try {
    payload = await apiRequest<unknown>('/attempts/history', { authenticated: true, signal })
  } catch (error) {
    // 主动取消交给调用方忽略，不当作错误态渲染。
    if (signal?.aborted) throw error
    if (error instanceof ApiError) {
      if (error.status === 401) return { ok: false, error: toError('unauthorized', 401, null) }
      if (error.status === 0) return { ok: false, error: toError('network', 0, null) }
      return { ok: false, error: toError('server', error.status, error.message) }
    }
    return { ok: false, error: toError('network', null, null) }
  }

  if (!isHistoryPayload(payload)) {
    return { ok: false, error: toError('server', null, '历史记录数据格式不正确，请稍后重试。') }
  }
  return { ok: true, items: payload.items }
}
