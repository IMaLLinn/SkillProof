import { scoreText, shortDimensionName } from '../../lib/reportUtils'
import type { DimensionDiff } from '../../lib/historyUtils'

const CENTER = 180
const RADIUS = 104
const LABEL_RADIUS = 138
const GRID_SCALES = [0.25, 0.5, 0.75, 1]

interface CompareRadarProps {
  items: DimensionDiff[]
  beforeLabel: string
  afterLabel: string
}

/**
 * 两次测评的六维叠加雷达图。
 * 维度顺序与配对由 DimensionDiff 保证，不依赖接口返回的数组顺序。
 */
export function CompareRadar({ items, beforeLabel, afterLabel }: CompareRadarProps) {
  const count = items.length
  if (count === 0) return null

  const pointAt = (index: number, scale: number): [number, number] => {
    const angle = (index * 2 * Math.PI) / count - Math.PI / 2
    return [
      CENTER + Math.cos(angle) * RADIUS * scale,
      CENTER + Math.sin(angle) * RADIUS * scale,
    ]
  }

  const clamp = (value: number) => Math.max(0, Math.min(100, value)) / 100

  const toPoints = (values: number[]): string =>
    values.map((value, index) => pointAt(index, clamp(value)).join(',')).join(' ')

  const describe = items
    .map((item) => `${item.name} 前 ${scoreText(item.before.score)} 分、后 ${scoreText(item.after.score)} 分`)
    .join('，')

  return (
    <figure className="compare-radar">
      <svg
        className="compare-radar__svg"
        viewBox="0 0 360 360"
        role="img"
        aria-label={`两次测评六维对比：${describe}`}
      >
        {GRID_SCALES.map((scale) => (
          <polygon
            key={scale}
            className="compare-radar__grid"
            points={items.map((_, index) => pointAt(index, scale).join(',')).join(' ')}
          />
        ))}

        {items.map((item, index) => {
          const [x, y] = pointAt(index, 1)
          const [labelX, labelY] = pointAt(index, LABEL_RADIUS / RADIUS)
          const anchor = Math.abs(labelX - CENTER) < 8 ? 'middle' : labelX > CENTER ? 'start' : 'end'
          return (
            <g key={item.id}>
              <line className="compare-radar__axis" x1={CENTER} y1={CENTER} x2={x} y2={y} />
              <text
                className="compare-radar__label"
                x={labelX}
                y={labelY}
                textAnchor={anchor}
                dominantBaseline="middle"
              >
                {shortDimensionName(item.after)}
              </text>
            </g>
          )
        })}

        <polygon
          className="compare-radar__area compare-radar__area--before"
          points={toPoints(items.map((item) => item.before.score))}
        />
        <polygon
          className="compare-radar__area compare-radar__area--after"
          points={toPoints(items.map((item) => item.after.score))}
        />

        {items.map((item, index) => {
          const [beforeX, beforeY] = pointAt(index, clamp(item.before.score))
          const [afterX, afterY] = pointAt(index, clamp(item.after.score))
          return (
            <g key={item.id}>
              <circle className="compare-radar__dot compare-radar__dot--before" cx={beforeX} cy={beforeY} r={3} />
              <circle className="compare-radar__dot compare-radar__dot--after" cx={afterX} cy={afterY} r={3.5} />
            </g>
          )
        })}
      </svg>

      <figcaption className="compare-radar__caption">
        <span className="compare-radar__legend">
          <span className="compare-radar__swatch compare-radar__swatch--before" aria-hidden="true" />
          {beforeLabel}
        </span>
        <span className="compare-radar__legend">
          <span className="compare-radar__swatch compare-radar__swatch--after" aria-hidden="true" />
          {afterLabel}
        </span>
        <span className="compare-radar__note">各维度满分 100 分，两条轮廓只描述两次抽题的作答差异。</span>
      </figcaption>
    </figure>
  )
}
