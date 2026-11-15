import { DIMENSION_ORDER, scoreText } from './reportUtils'
import type { HistoryItem } from '../types/history'
import type { ReportDimension } from '../types/report'

/** 无法进入对比的原因，页面据此给出具体提示而不是笼统失败。 */
export type CompareBlockReason =
  | 'sameAttempt'
  | 'differentRole'
  | 'notSubmitted'
  | 'incompleteDimensions'

/** 可以对比但需要说明的版本差异，对应 api.md 中「对比限制」的约定。 */
export type CompareLimitation =
  | 'scoringRule'
  | 'blueprintRule'
  | 'questionBank'
  | 'questionBankUnknown'
  | 'reusedQuestions'

export interface DimensionDiff {
  id: string
  name: string
  before: ReportDimension
  after: ReportDimension
  /** 后一次减前一次，已按两位小数消除浮点误差。 */
  delta: number
}

export interface Comparison {
  before: HistoryItem
  after: HistoryItem
  dimensions: DimensionDiff[]
  limitations: CompareLimitation[]
  /** 评分规则或抽题规则不同时不展示直接差值，只并列两次分数。 */
  diffAllowed: boolean
}

export type ComparisonResult =
  | { ok: true; comparison: Comparison }
  | { ok: false; reason: CompareBlockReason }

export const BLOCK_TEXT: Record<CompareBlockReason, string> = {
  sameAttempt: '同一次测评不能与自身对比，请选择另外一条已提交记录。',
  differentRole: '只能对比同一岗位的两次测评，请选择相同岗位的记录。',
  notSubmitted: '进行中的测评还没有结果，提交后才能参与对比。',
  incompleteDimensions: '所选记录缺少完整六维分数（可能快照损坏或题库版本未知），暂时无法对比。',
}

export const LIMITATION_TEXT: Record<CompareLimitation, string> = {
  scoringRule: '两次测评使用的评分规则版本不同，分数不可直接相减，仅并列展示各自得分。',
  blueprintRule: '两次测评的抽题蓝图版本不同，题目结构可能变化，分数不可直接相减。',
  questionBank: '两次测评的题库版本不同，题目覆盖范围可能有差异，差值只反映本次抽到的题目。',
  questionBankUnknown: '其中一次记录无法确定当时的题库版本，题目覆盖范围未知。',
  reusedQuestions: '两次测评存在重复题目，重复作答会抬高分数，差值可能被放大。',
}

/** 分数按两位小数取整，避免 83.33 - 66.67 这类浮点误差把持平显示成负值。 */
export function roundScore(value: number): number {
  return Math.round(value * 100) / 100
}

export type DeltaKind = 'up' | 'down' | 'flat'

export function deltaKind(delta: number): DeltaKind {
  if (delta > 0) return 'up'
  if (delta < 0) return 'down'
  return 'flat'
}

export function deltaText(delta: number): string {
  const kind = deltaKind(delta)
  if (kind === 'flat') return '±0'
  return kind === 'up' ? `+${scoreText(delta)}` : scoreText(delta)
}

/** 六维摘要是否完整可用；进行中或快照损坏的记录为 null。 */
export function hasCompleteDimensions(item: HistoryItem): item is HistoryItem & { dimensions: ReportDimension[] } {
  const { dimensions } = item
  if (!Array.isArray(dimensions) || dimensions.length !== DIMENSION_ORDER.length) return false
  return DIMENSION_ORDER.every((id) => dimensions.some((dimension) => dimension.id === id))
}

/** 能否作为对比候选：已提交且六维完整。 */
export function canCompare(item: HistoryItem): boolean {
  return item.status === 'submitted' && hasCompleteDimensions(item)
}

/** 时间早的作为基准，晚的作为对比对象；创建时间相同时按 id 保证顺序稳定。 */
function chronological(a: HistoryItem, b: HistoryItem): [HistoryItem, HistoryItem] {
  const timeA = Date.parse(a.createdAt)
  const timeB = Date.parse(b.createdAt)
  if (Number.isNaN(timeA) || Number.isNaN(timeB) || timeA === timeB) {
    return a.id <= b.id ? [a, b] : [b, a]
  }
  return timeA < timeB ? [a, b] : [b, a]
}

function dimensionById(dimensions: ReportDimension[], id: string): ReportDimension | undefined {
  return dimensions.find((item) => item.id === id)
}

/**
 * 构造同岗位两次已提交结果的对比。
 * 差值为后一次减前一次；评分规则或抽题规则不同时只并列分数，不计算差值。
 */
export function buildComparison(a: HistoryItem, b: HistoryItem): ComparisonResult {
  if (a.id === b.id) return { ok: false, reason: 'sameAttempt' }
  if (a.roleId !== b.roleId) return { ok: false, reason: 'differentRole' }
  if (a.status !== 'submitted' || b.status !== 'submitted') return { ok: false, reason: 'notSubmitted' }
  if (!hasCompleteDimensions(a)) return { ok: false, reason: 'incompleteDimensions' }
  if (!hasCompleteDimensions(b)) return { ok: false, reason: 'incompleteDimensions' }

  const [before, after] = chronological(a, b)
  const beforeDims: ReportDimension[] = before.id === a.id ? a.dimensions : b.dimensions
  const afterDims: ReportDimension[] = before.id === a.id ? b.dimensions : a.dimensions

  const dimensions: DimensionDiff[] = []
  for (const id of DIMENSION_ORDER) {
    const previous = dimensionById(beforeDims, id)
    const current = dimensionById(afterDims, id)
    if (!previous || !current) return { ok: false, reason: 'incompleteDimensions' }
    dimensions.push({
      id,
      name: current.name,
      before: previous,
      after: current,
      delta: roundScore(current.score - previous.score),
    })
  }

  const limitations: CompareLimitation[] = []
  if (before.modelVersion !== after.modelVersion) limitations.push('scoringRule')
  if (before.blueprintVersion !== after.blueprintVersion) limitations.push('blueprintRule')
  if (before.questionBankVersion === null || after.questionBankVersion === null) {
    limitations.push('questionBankUnknown')
  } else if (before.questionBankVersion !== after.questionBankVersion) {
    limitations.push('questionBank')
  }
  if (before.reusedQuestionCount > 0 || after.reusedQuestionCount > 0) limitations.push('reusedQuestions')

  const diffAllowed = before.modelVersion === after.modelVersion
    && before.blueprintVersion === after.blueprintVersion

  return { ok: true, comparison: { before, after, dimensions, limitations, diffAllowed } }
}

export interface RoleGroup {
  roleId: string
  roleName: string
  items: HistoryItem[]
  /** 该岗位已提交且六维完整的记录数，用于提示「只有一次记录无法对比」。 */
  comparableCount: number
}

/** 按岗位分组，组内保持接口返回的时间倒序；岗位顺序按最近一次测评时间排列。 */
export function groupByRole(items: HistoryItem[]): RoleGroup[] {
  const groups: RoleGroup[] = []
  for (const item of items) {
    let group = groups.find((candidate) => candidate.roleId === item.roleId)
    if (!group) {
      group = { roleId: item.roleId, roleName: item.roleName, items: [], comparableCount: 0 }
      groups.push(group)
    }
    group.items.push(item)
    if (canCompare(item)) group.comparableCount += 1
  }
  return groups
}

export function statusText(item: HistoryItem): string {
  return item.status === 'submitted' ? '已提交' : '进行中'
}
