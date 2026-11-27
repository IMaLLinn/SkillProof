import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  fetchWrongDetail, fetchWrongQuestions, saveMastery, submitPractice,
  type WrongDetail, type WrongList, type WrongQuery, type WrongStatus,
} from '../../lib/wrongbookApi'
import '../../styles/wrongbook.css'

const INITIAL_QUERY: WrongQuery = { roleId: '', dimension: '', topicId: '', status: 'review', offset: 0 }
const STATUS_LABELS: Record<WrongStatus, string> = { review: '待复习', mastered: '已掌握', all: '全部' }
const dateText = (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false })
const messageOf = (error: unknown) => error instanceof Error ? error.message : '操作失败，请稍后重试'

export function WrongbookPage({ onBack, onOpenReport }: {
  onBack: () => void; onOpenReport: (id: string) => void
}) {
  const [query, setQuery] = useState(INITIAL_QUERY)
  const [data, setData] = useState<WrongList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<WrongDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [detailRevision, setDetailRevision] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    fetchWrongQuestions(query, controller.signal).then((result) => {
      if (!controller.signal.aborted) setData(result)
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(messageOf(reason))
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [query, revision])

  useEffect(() => {
    if (!selectedId) return
    const controller = new AbortController()
    fetchWrongDetail(selectedId, controller.signal).then((result) => {
      if (!controller.signal.aborted) setDetail(result)
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setDetailError(messageOf(reason))
    }).finally(() => {
      if (!controller.signal.aborted) setDetailLoading(false)
    })
    return () => controller.abort()
  }, [selectedId, detailRevision])

  function changeQuery(patch: Partial<WrongQuery>) {
    setLoading(true)
    setError('')
    setSelectedId(null)
    setDetail(null)
    setQuery((current) => ({ ...current, ...patch }))
  }

  function selectQuestion(id: string) {
    if (selectedId === id && detail) return
    setDetail(null)
    setDetailError('')
    setDetailLoading(true)
    if (selectedId === id) setDetailRevision((value) => value + 1)
    else setSelectedId(id)
  }

  function refreshList() {
    setError('')
    setLoading(true)
    setRevision((value) => value + 1)
  }

  const facets = data?.filters ?? []
  const roles = [...new Map(facets.map((item) => [item.roleId, item])).values()]
  const dimensions = [...new Map(facets.filter((item) => !query.roleId || item.roleId === query.roleId)
    .map((item) => [item.dimension, item])).values()]
  const topics = [...new Map(facets.filter((item) => (!query.roleId || item.roleId === query.roleId)
    && (!query.dimension || item.dimension === query.dimension)).map((item) => [item.topicId, item])).values()]

  return (
    <main className={`wrongbook-page${selectedId ? ' wrongbook-page--detail' : ''}`}>
      <header className="wrongbook-header">
        <button type="button" className="wb-link" onClick={onBack}>← 返回岗位选择</button>
        <h1>错题本</h1>
        <p>回看测评中的错题，重新作答，再确认是否掌握。</p>
      </header>
      <nav className="wb-statuses" aria-label="错题状态">
        {(['review', 'mastered', 'all'] as const).map((status) => (
          <button key={status} type="button" aria-pressed={query.status === status}
            onClick={() => changeQuery({ status, offset: 0 })}>
            {STATUS_LABELS[status]}{data ? ` ${data.counts[status]}` : ''}
          </button>
        ))}
      </nav>
      <form className="wb-filters" onSubmit={(event) => event.preventDefault()} aria-label="筛选错题">
        <label>岗位<select value={query.roleId} onChange={(event) => changeQuery({
          roleId: event.target.value, dimension: '', topicId: '', offset: 0,
        })}><option value="">全部岗位</option>{roles.map((item) => <option key={item.roleId} value={item.roleId}>{item.roleName}</option>)}</select></label>
        <label>能力维度<select value={query.dimension} onChange={(event) => changeQuery({
          dimension: event.target.value, topicId: '', offset: 0,
        })}><option value="">全部维度</option>{dimensions.map((item) => <option key={item.dimension} value={item.dimension}>{item.dimensionName}</option>)}</select></label>
        <label>知识点<select value={query.topicId} onChange={(event) => changeQuery({ topicId: event.target.value, offset: 0 })}>
          <option value="">全部知识点</option>{topics.map((item) => <option key={item.topicId} value={item.topicId}>{item.topic}</option>)}
        </select></label>
        <button type="button" className="wb-link" onClick={() => changeQuery(INITIAL_QUERY)}>清除筛选</button>
      </form>
      {error && <div className="wb-notice" role="alert"><p>{error}</p><button type="button" onClick={refreshList}>重新加载</button></div>}
      <div className="wb-workspace">
        <section className="wb-index" aria-label="错题列表" aria-busy={loading}>
          <p className="wb-list-count" role="status">{loading ? '正在加载错题…' : `共 ${data?.total ?? 0} 条`}</p>
          {!loading && !error && data?.items.length === 0 && <div className="wb-empty">
            <h2>{data.counts.all === 0 ? '还没有收集到错题' : '当前筛选下没有错题'}</h2>
            <p>{data.counts.all === 0 ? '本功能启用后，提交测评中的错题会自动保存在这里。' : '可以切换状态或清除筛选，查看其他记录。'}</p>
          </div>}
          <ul>{data?.items.map((item) => <li key={item.id}>
            <button type="button" className="wb-record" aria-pressed={selectedId === item.id} onClick={() => selectQuestion(item.id)}>
              <span className="wb-record-meta">{item.dimensionName} · {item.roleName}</span>
              <strong>{item.stem}</strong>
              <span>{item.topic}</span>
              <span className="wb-record-footer">{dateText(item.collectedAt)}<span>{item.mastered ? '已掌握' : '待复习'} · 重练 {item.practiceCount} 次</span></span>
            </button>
          </li>)}</ul>
          {data && data.total > data.limit && <nav className="wb-pagination" aria-label="错题分页">
            <button type="button" disabled={loading || query.offset === 0} onClick={() => changeQuery({ offset: Math.max(0, query.offset - data.limit) })}>上一页</button>
            <span>{Math.floor(query.offset / data.limit) + 1} / {Math.ceil(data.total / data.limit)}</span>
            <button type="button" disabled={loading || query.offset + data.limit >= data.total} onClick={() => changeQuery({ offset: query.offset + data.limit })}>下一页</button>
          </nav>}
        </section>
        <section className="wb-detail" aria-label="错题详情" aria-busy={detailLoading}>
          {selectedId && <button type="button" className="wb-link wb-mobile-back" onClick={() => { setSelectedId(null); setDetail(null) }}>← 返回错题列表</button>}
          {!selectedId && <div className="wb-empty"><h2>选择一道错题</h2><p>查看当时的作答和解析，或开始一轮重练。</p></div>}
          {detailLoading && <p role="status">正在加载题目…</p>}
          {detailError && <div role="alert"><p>{detailError}</p><button type="button" onClick={() => selectedId && selectQuestion(selectedId)}>重试</button></div>}
          {detail && !detailLoading && <QuestionDetail key={detail.id} detail={detail} onOpenReport={onOpenReport}
            onUpdated={(updated) => { setDetail(updated); refreshList() }} />}
        </section>
      </div>
    </main>
  )
}

function QuestionDetail({ detail, onUpdated, onOpenReport }: {
  detail: WrongDetail; onUpdated: (detail: WrongDetail) => void; onOpenReport: (id: string) => void
}) {
  const [mode, setMode] = useState<'review' | 'practice' | 'result'>('review')
  const [selected, setSelected] = useState<string[]>([])
  const [requestId, setRequestId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<boolean | null>(null)
  const { question } = detail

  function startPractice() {
    setMode('practice')
    setSelected([])
    setRequestId(crypto.randomUUID())
    setError('')
    setResult(null)
  }

  async function practice(event: FormEvent) {
    event.preventDefault()
    if (busy || selected.length === 0) return
    setBusy(true)
    setError('')
    try {
      const saved = await submitPractice(detail.id, selected, requestId)
      onUpdated(saved.item)
      setResult(saved.result.isCorrect)
      setMode('result')
    } catch (reason: unknown) { setError(messageOf(reason)) }
    finally { setBusy(false) }
  }

  async function changeMastery() {
    if (busy) return
    setBusy(true)
    setError('')
    try { onUpdated(await saveMastery(detail.id, !detail.mastered)) }
    catch (reason: unknown) { setError(messageOf(reason)) }
    finally { setBusy(false) }
  }

  return <>
    <div className="wb-detail-meta"><span>{detail.dimensionName} · {detail.topic}</span><span>{detail.mastered ? '已掌握' : '待复习'}</span></div>
    <h2 className="wb-stem">{question.stem}</h2>
    <p className="wb-origin">{detail.roleName} · {question.type === 'single' ? '单选题' : '多选题'} · 题目版本 {question.version}</p>
    <p className="wb-origin">来源测评提交于 {dateText(detail.collectedAt)} <button type="button" className="wb-link" onClick={() => onOpenReport(detail.attemptId)}>查看原报告</button></p>
    {error && <p className="wb-notice" role="alert">{error}</p>}
    {mode === 'practice' ? <form onSubmit={(event) => void practice(event)} aria-label="错题重练">
      <fieldset disabled={busy}><legend>{question.type === 'multiple' ? '请选择所有正确选项' : '请选择一个答案'}</legend>
        {question.options.map((option) => <label className="wb-option" key={option.id}>
          <input type={question.type === 'single' ? 'radio' : 'checkbox'} name="practice-answer" value={option.id}
            checked={selected.includes(option.id)} onChange={() => setSelected((current) => question.type === 'single'
              ? [option.id] : current.includes(option.id) ? current.filter((id) => id !== option.id) : [...current, option.id])} />
          <span><strong>{option.id}.</strong> {option.text}</span>
        </label>)}
      </fieldset>
      <div className="wb-actions"><button type="submit" className="wb-primary" disabled={busy || selected.length === 0}>{busy ? '正在保存…' : '提交重练答案'}</button>
        <button type="button" disabled={busy} onClick={() => { setMode('review'); setError('') }}>取消重练</button></div>
    </form> : <>
      {mode === 'result' && <p className={`wb-result ${result ? 'wb-result--correct' : ''}`} role="status">{result ? '本次重练回答正确。' : '本次重练回答有误，可以对照解析再试一次。'} 已记录，累计重练 {detail.practiceCount} 次。</p>}
      <ul className="wb-options">{question.options.map((option) => <li key={option.id} className={question.correct.includes(option.id) ? 'wb-option--correct' : ''}>
        <span><strong>{option.id}.</strong> {option.text}</span><span className="wb-option-tags">{question.correct.includes(option.id) && '正确选项'}{detail.originalAnswer.includes(option.id) && ' · 原测评选择'}</span>
      </li>)}</ul>
      <dl className="wb-answers"><div><dt>原测评答案</dt><dd>{detail.originalAnswer.join('、') || '未作答'}</dd></div><div><dt>正确答案</dt><dd>{question.correct.join('、')}</dd></div></dl>
      <h3>答案解析</h3><p className="wb-explanation">{question.explanation}</p>
      {question.sources.length > 0 && <details className="wb-sources"><summary>题目资料来源</summary><ul>{question.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title} ↗</a></li>)}</ul></details>}
      <div className="wb-actions"><button type="button" className="wb-primary" disabled={busy} onClick={startPractice}>{mode === 'result' ? '再练一次' : '重练这道题'}</button>
        <button type="button" disabled={busy} onClick={() => void changeMastery()}>{detail.mastered ? '移回待复习' : '标记为已掌握'}</button></div>
      <p className="wb-origin">重练不会修改原测评成绩。掌握状态由你确认，不会因答对一次自动改变。</p>
    </>}
    <details className="wb-practices"><summary>重练记录（{detail.practiceCount} 次）</summary>
      {detail.practices.length === 0 ? <p>尚未重练这道题。</p> : <ol>{detail.practices.map((item) => <li key={item.id}>
        <span>{dateText(item.createdAt)}</span><span>选择 {item.selected.join('、')}</span><strong>{item.isCorrect ? '正确' : '错误'}</strong>
      </li>)}</ol>}
    </details>
  </>
}
