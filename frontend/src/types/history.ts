import type { ReportDimension } from './report'

/** 测评状态，与 docs/design/api.md 中 attempts.status 的取值一致。 */
export type AttemptStatus = 'in_progress' | 'submitted'

/**
 * 历史测评列表中的一条记录，字段对应 GET /api/attempts/history 的返回项。
 * 分数与六维摘要只来自服务端报告快照，进行中或快照损坏时为 null。
 */
export interface HistoryItem {
  id: string
  roleId: string
  roleName: string
  status: AttemptStatus
  createdAt: string
  /** 进行中记录为 null。 */
  submittedAt: string | null
  /** 已提交记录沿用测评 ID 作为报告 ID；进行中为 null。 */
  reportId: string | null
  /** 综合分，0–100；进行中或快照损坏为 null。 */
  score: number | null
  /** 六维摘要，按维度 ID 对应；进行中或快照损坏为 null。 */
  dimensions: ReportDimension[] | null
  modelVersion: string
  /** 抽题时保存的题库版本；迁移前的旧记录为 null。 */
  questionBankVersion: string | null
  blueprintVersion: string
  reusedQuestionCount: number
}
