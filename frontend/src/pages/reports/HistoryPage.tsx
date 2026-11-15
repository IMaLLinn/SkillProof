import { useEffect, useState } from 'react'
import { ApiError } from '../../api'
import { CompareRadar } from '../../components/reports/CompareRadar'
import { fetchHistory } from '../../lib/historyApi'
import type { HistoryLoadError } from '../../lib/historyApi'
import {
  BLOCK_TEXT,
  LIMITATION_TEXT,
  buildComparison,
  canCompare,
  deltaKind,
  deltaText,
  groupByRole,
  statusText,
} from '../../lib/historyUtils'
import { dateText, scoreText } from '../../lib/reportUtils'
import type { HistoryItem } from '../../types/history'
import '../../styles/history.css'

type PageState =
  | { status: 'loading' }
  | { status: 'ready'; items: HistoryItem[] }
  | { status: 'error'; error: HistoryLoadError }

type StatusFilter = 'all' | 'in_progress' | 'submitted'

const ERROR_TITLE: Record<HistoryLoadError['kind'], string> = {
  unauthorized: '需要登录后查看历史记录',
  network: '网络连接失败',
  server: '历史记录加载失败',
}

interface HistoryPageProps {
  onBack: () => void
  onOpenReport: (reportId: string) => void
  onOpenAttempt: (attemptId: string) => void
  onRetest: (roleId: string) => Promise<void>
}

export function HistoryPage({ onBack, onOpenReport, onOpenAttempt, onRetest }: HistoryPageProps) {
  const [state, setState] = useState<PageState>({ status: 'loading' })
  const [reloadToken, setReloadToken] = useState(0)
  const [roleFilter, setRoleFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [retestingRoleId, setRetestingRoleId] = useState<string | null>(null)
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    fetchHistory(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setState(result.ok ? { status: 'ready', items: result.items } : { status: 'error', error: result.error })
        if (result.ok) setSelectedIds([])
      })
      .catch(() => {
        // 主动取消（切换页面或组件卸载）不更新界面。
      })

    return () => controller.abort()
  }, [reloadToken])

  const retry = () => {
    setState({ status: 'loading' })
    setReloadToken((value) => value + 1)
  }

  if (state.status === 'loading') {
    return (
      <main className="history-page" aria-busy="true">
        <p className="history-state__hint">正在加载历史测评记录…</p>
        <div className="history-skeleton" />
        <div className="history-skeleton" />
        <div className="history-skeleton history-skeleton--short" />
      </main>
    )
  }

  if (state.status === 'error') {
    const { error } = state
    const retryable = error.kind === 'network' || error.kind === 'server'
    return (
      <main className="history-page">
        <div className="history-state" role="alert">
          <h1 className="history-state__title">{ERROR_TITLE[error.kind]}</h1>
          <p className="history-state__message">{error.message}</p>
          {error.kind === 'unauthorized' && (
            <p className="history-state__hint">请返回登录页重新登录后，再查看历史测评记录。</p>
          )}
          <div className="history-state__actions">
            {retryable && <button type="button" className="history-button" onClick={retry}>重新加载</button>}
            <button type="button" className="history-button history-button--ghost" onClick={onBack}>返回岗位选择</button>
          </div>
        </div>
      </main>
    )
  }

  const { items } = state
  const roleOptions = items.reduce<{ roleId: string; roleName: string }[]>((acc, item) => {
    if (!acc.some((option) => option.roleId === item.roleId)) {
      acc.push({ roleId: item.roleId, roleName: item.roleName })
    }
    return acc
  }, [])

  const filtered = items.filter(
    (item) =>
      (roleFilter === 'all' || item.roleId === roleFilter)
      && (statusFilter === 'all' || item.status === statusFilter),
  )
  const groups = groupByRole(filtered)

  const selectedItems = selectedIds
    .map((id) => items.find((item) => item.id === id))
    .filter((item): item is HistoryItem => item !== undefined)
  const comparison = selectedItems.length === 2 ? buildComparison(selectedItems[0], selectedItems[1]) : null

  const toggleSelect = (item: HistoryItem) => {
    if (!canCompare(item)) return
    setSelectedIds((previous) => {
      if (previous.includes(item.id)) return previous.filter((id) => id !== item.id)
      if (previous.length >= 2) return previous
      return [...previous, item.id]
    })
  }

  async function retest(roleId: string) {
    if (retestingRoleId !== null) return
    setRetestingRoleId(roleId)
    setActionError('')
    try {
      await onRetest(roleId)
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : '复测创建失败，请稍后重试')
    } finally {
      setRetestingRoleId(null)
    }
  }

  return (
    <main className="history-page">
      <header className="history-header">
        <button type="button" className="history-back" onClick={onBack}>← 返回岗位选择</button>
        <p className="history-header__eyebrow">历史测评</p>
        <h1 className="history-header__title">历次测评与复测对比</h1>
        <p className="history-header__meta">只显示当前账号的记录，按创建时间从新到旧排列。</p>
      </header>

      {actionError && <p className="history-alert" role="alert">{actionError}</p>}

      {items.length === 0 ? (
        <div className="history-state">
          <h2 className="history-state__title">还没有测评记录</h2>
          <p className="history-state__message">完成一次测评并提交后，结果会出现在这里，之后可以复测并对比两次表现。</p>
          <div className="history-state__actions">
            <button type="button" className="history-button" onClick={onBack}>去选择岗位</button>
          </div>
        </div>
      ) : (
        <>
          <section className="history-filters" aria-label="筛选历史记录">
            <label className="history-field">
              <span className="history-field__label">岗位</span>
              <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
                <option value="all">全部岗位</option>
                {roleOptions.map((option) => (
                  <option key={option.roleId} value={option.roleId}>{option.roleName}</option>
                ))}
              </select>
            </label>
            <label className="history-field">
              <span className="history-field__label">状态</span>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
              >
                <option value="all">全部状态</option>
                <option value="submitted">已提交</option>
                <option value="in_progress">进行中</option>
              </select>
            </label>
            <p className="history-filters__count" role="status">
              共 {filtered.length} 条记录
            </p>
          </section>

          {filtered.length === 0 && (
            <div className="history-state">
              <h2 className="history-state__title">当前筛选条件下没有记录</h2>
              <p className="history-state__message">换一个岗位或状态，或者清除筛选查看全部记录。</p>
              <div className="history-state__actions">
                <button
                  type="button"
                  className="history-button history-button--ghost"
                  onClick={() => {
                    setRoleFilter('all')
                    setStatusFilter('all')
                  }}
                >
                  清除筛选
                </button>
              </div>
            </div>
          )}

          {groups.map((group) => (
            <section className="history-group" key={group.roleId} aria-labelledby={`history-group-${group.roleId}`}>
              <div className="history-group__head">
                <h2 className="history-group__title" id={`history-group-${group.roleId}`}>{group.roleName}</h2>
                <button
                  type="button"
                  className="history-button history-button--small"
                  disabled={retestingRoleId !== null}
                  onClick={() => retest(group.roleId)}
                >
                  {retestingRoleId === group.roleId ? '正在创建复测…' : '复测该岗位'}
                </button>
              </div>

              {group.comparableCount === 1 && (
                <p className="history-group__hint">
                  该岗位只有一次可对比的已提交记录，完成一次复测后即可对比两次结果。
                </p>
              )}

              <ul className="history-list">
                {group.items.map((item) => {
                  const reportId = item.reportId
                  const selectable = canCompare(item)
                  return (
                    <li key={item.id}>
                      <article className="history-item">
                        <div className="history-item__head">
                          <span className={`history-badge history-badge--${item.status}`}>{statusText(item)}</span>
                          <p className="history-item__time">
                            创建 {dateText(item.createdAt)}
                            {item.submittedAt ? ` · 提交 ${dateText(item.submittedAt)}` : ''}
                          </p>
                        </div>

                        <div className="history-item__score">
                          <span className="history-item__score-label">综合分</span>
                          <strong className="history-item__score-value">
                            {item.status === 'submitted'
                              ? item.score === null ? '不可用' : scoreText(item.score)
                              : '—'}
                          </strong>
                        </div>

                        <p className="history-item__version">
                          题库版本 {item.questionBankVersion ?? '未知'}
                          {' · '}评分规则 {item.modelVersion}
                          {' · '}抽题蓝图 {item.blueprintVersion}
                          {item.reusedQuestionCount > 0 ? ` · 重复题 ${item.reusedQuestionCount} 道` : ''}
                        </p>

                        {item.status === 'submitted' && item.score === null && (
                          <p className="history-item__warning">
                            这次结果的分数快照不可用，无法查看详情，也不能参与对比。
                          </p>
                        )}

                        <div className="history-item__actions">
                          {item.status === 'in_progress' && (
                            <button type="button" className="history-button history-button--small" onClick={() => onOpenAttempt(item.id)}>
                              继续作答
                            </button>
                          )}
                          {reportId !== null && item.score !== null && (
                            <button type="button" className="history-button history-button--small" onClick={() => onOpenReport(reportId)}>
                              查看结果
                            </button>
                          )}
                          {selectable && (
                            <label className="history-select">
                              <input
                                type="checkbox"
                                checked={selectedIds.includes(item.id)}
                                disabled={!selectedIds.includes(item.id) && selectedIds.length >= 2}
                                onChange={() => toggleSelect(item)}
                              />
                              加入对比
                            </label>
                          )}
                        </div>
                      </article>
                    </li>
                  )
                })}
              </ul>
            </section>
          ))}

          <section className="history-compare" aria-labelledby="history-compare-title">
            <div className="history-compare__head">
              <h2 className="history-compare__title" id="history-compare-title">两次结果对比</h2>
              {selectedIds.length > 0 && (
                <button type="button" className="history-button history-button--ghost history-button--small" onClick={() => setSelectedIds([])}>
                  清空选择
                </button>
              )}
            </div>

            {selectedIds.length === 0 && (
              <p className="history-compare__hint">
                在上面的列表里勾选两条<strong>同岗位、已提交</strong>的记录，即可查看六维对比。
              </p>
            )}

            {selectedIds.length === 1 && (
              <p className="history-compare__hint">已选择 1 条，再选择一条同岗位的已提交记录进行对比。</p>
            )}

            {comparison !== null && !comparison.ok && (
              <p className="history-compare__blocked" role="alert">{BLOCK_TEXT[comparison.reason]}</p>
            )}

            {comparison !== null && comparison.ok && (
              <div className="history-compare__body">
                <p className="history-compare__summary">
                  <span>
                    基准：{scoreText(comparison.comparison.before.score)} 分 ·{' '}
                    {dateText(comparison.comparison.before.submittedAt)}
                  </span>
                  <span>
                    对比：{scoreText(comparison.comparison.after.score)} 分 ·{' '}
                    {dateText(comparison.comparison.after.submittedAt)}
                  </span>
                </p>

                <div className="history-compare__charts">
                  <CompareRadar
                    items={comparison.comparison.dimensions}
                    beforeLabel={`基准 ${scoreText(comparison.comparison.before.score)} 分`}
                    afterLabel={`对比 ${scoreText(comparison.comparison.after.score)} 分`}
                  />
                </div>

                <div className="history-compare__table-wrap">
                  <table className="history-compare__table">
                    <caption className="history-visually-hidden">两次测评各维度得分与差值</caption>
                    <thead>
                      <tr>
                        <th scope="col">知识维度</th>
                        <th scope="col">基准</th>
                        <th scope="col">对比</th>
                        {comparison.comparison.diffAllowed && <th scope="col">差值</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {comparison.comparison.dimensions.map((item) => (
                        <tr key={item.id}>
                          <th scope="row">{item.name}</th>
                          <td>{scoreText(item.before.score)}</td>
                          <td>{scoreText(item.after.score)}</td>
                          {comparison.comparison.diffAllowed && (
                            <td className={`history-delta history-delta--${deltaKind(item.delta)}`}>
                              {deltaText(item.delta)}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="history-compare__table-hint">表格可左右滑动查看完整列</p>

                {comparison.comparison.limitations.length > 0 && (
                  <ul className="history-compare__limits">
                    {comparison.comparison.limitations.map((limitation) => (
                      <li key={limitation}>{LIMITATION_TEXT[limitation]}</li>
                    ))}
                  </ul>
                )}

                <p className="history-compare__notice">
                  差值只描述这两次抽题的作答差异，可能受题目难度、题库覆盖和重复题影响，
                  不代表能力提升或下降的因果结论，也不代表岗位胜任力。
                </p>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  )
}
