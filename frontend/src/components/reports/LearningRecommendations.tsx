import { Fragment, useEffect, useState } from 'react'
import { fetchRecommendations, type Recommendation } from '../../lib/reportApi'
import '../../styles/recommendations.css'

type State =
  | { status: 'loading' }
  | { status: 'ready'; items: Recommendation[] }
  | { status: 'error' }

export function LearningRecommendations({ attemptId }: { attemptId: string }) {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    fetchRecommendations(attemptId, controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setState({ status: 'ready', items })
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: 'error' })
      })
    return () => controller.abort()
  }, [attemptId, retry])

  function reload() {
    setState({ status: 'loading' })
    setRetry((value) => value + 1)
  }

  return (
    <section className="result-section" aria-labelledby="result-learning-title">
      <h2 className="result-section__title" id="result-learning-title">学习建议</h2>
      {state.status === 'loading' && (
        <p className="result-empty" role="status">正在加载学习建议…</p>
      )}
      {state.status === 'error' && (
        <div className="result-empty learning-status">
          <p role="status">暂时无法加载学习建议。</p>
          <button type="button" className="result-state__action" onClick={reload}>重试</button>
        </div>
      )}
      {state.status === 'ready' && state.items.length === 0 && (
        <p className="result-empty" role="status">本次暂无学习建议。</p>
      )}
      {state.status === 'ready' && state.items.length > 0 && (
        <p className="learning-intro">按本次得分较低的维度，选几个知识点先复习。</p>
      )}
      {state.status === 'ready' && state.items.map((dimension) => (
        <div className="learning-group" key={dimension.id}>
          <header className="learning-group-header">
            <h3>{dimension.name}</h3>
            <p>{dimension.description}</p>
          </header>
          <ul className="learning-list">
            {dimension.resources.map((resource) => (
              <li className="learning-resource" key={resource.topicId}>
                <div className="learning-resource-main">
                  <h4>{resource.title}</h4>
                  <p className="learning-copy">{resource.summary}</p>
                </div>
                <div className="learning-action">
                  <a className="learning-reference" href={resource.url} target="_blank" rel="noopener noreferrer">
                    打开资料 <span aria-hidden="true">↗</span>
                    <span className="result-visually-hidden">（{resource.topic}，在新标签页打开）</span>
                  </a>
                  <p>{resource.source}</p>
                </div>
                <details className="learning-practice">
                  <summary>练习建议<span className="result-visually-hidden">：{resource.topic}</span></summary>
                  <div className="learning-practice-body">
                    <p>
                      {resource.exercise.split('\n').map((line, index) => (
                        <Fragment key={index}>
                          {index > 0 && <br />}
                          {line}
                        </Fragment>
                      ))}
                    </p>
                    <p className="learning-expected">
                      <strong>预期结果</strong><br />
                      {resource.expectedResult}
                    </p>
                  </div>
                </details>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}
