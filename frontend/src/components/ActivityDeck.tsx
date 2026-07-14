import { useMemo, useState } from 'react'
import activity from '../data/activity.json'

type ActivityKind = 'codex' | 'github'

type HeatmapDay = {
  date: string
  count: number
  level: number
  isFuture: boolean
}

const DAY_MS = 86_400_000
const WEEK_COUNT = 53

function dateAtNoon(value: string): Date {
  return new Date(`${value}T12:00:00`)
}

function isoDate(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumFractionDigits: value >= 1_000_000_000 ? 2 : 1,
  }).format(value)
}

function formatDate(value: string): string {
  return dateAtNoon(value).toLocaleDateString('en', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function quantile(sorted: number[], fraction: number): number {
  return sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * fraction))] ?? 0
}

function buildCalendar(kind: ActivityKind): HeatmapDay[][] {
  const sourceDays = kind === 'codex'
    ? activity.codex.days.map((day) => ({ date: day.date, count: day.tokens }))
    : activity.github.days
  const counts = sourceDays.map((day) => day.count).filter(Boolean).sort((a, b) => a - b)
  const thresholds = [
    quantile(counts, 0.2),
    quantile(counts, 0.45),
    quantile(counts, 0.7),
    quantile(counts, 0.9),
  ]
  const byDate = new Map(sourceDays.map((day) => [day.date, day.count]))
  const lastDataDay = dateAtNoon(activity.period.end)
  const calendarEnd = new Date(lastDataDay)
  calendarEnd.setDate(calendarEnd.getDate() + (6 - calendarEnd.getDay()))
  const calendarStart = new Date(calendarEnd.getTime() - ((WEEK_COUNT * 7 - 1) * DAY_MS))

  return Array.from({ length: WEEK_COUNT }, (_, weekIndex) =>
    Array.from({ length: 7 }, (_, dayIndex) => {
      const date = new Date(calendarStart.getTime() + ((weekIndex * 7 + dayIndex) * DAY_MS))
      const dateKey = isoDate(date)
      const count = byDate.get(dateKey) ?? 0
      const level = count === 0 ? 0 : 1 + thresholds.filter((threshold) => count > threshold).length
      return { date: dateKey, count, level, isFuture: date > lastDataDay }
    }),
  )
}

function monthMarkers(weeks: HeatmapDay[][]): Array<{ week: number; label: string }> {
  const markers: Array<{ week: number; label: string }> = []
  let previousMonth = ''
  weeks.forEach((week, index) => {
    const first = dateAtNoon(week[0].date)
    const middle = new Date(first.getTime() + 3 * DAY_MS)
    const month = `${middle.getFullYear()}-${middle.getMonth()}`
    if (month !== previousMonth) {
      markers.push({ week: index + 1, label: middle.toLocaleDateString('en', { month: 'short' }) })
      previousMonth = month
    }
  })
  return markers
}

function CodexMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.7 14.3 9.7 21.3 12l-7 2.3-2.3 7-2.3-7-7-2.3 7-2.3L12 2.7Z" />
    </svg>
  )
}

function GitHubMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 5v11.2M16 7.8v11.1M8 8.1h5.2A2.8 2.8 0 0 0 16 5.3V3m-8 13.2A2.8 2.8 0 1 1 5.2 19 2.8 2.8 0 0 1 8 16.2Zm8 2.7a2.8 2.8 0 1 1-2.8 2.8 2.8 2.8 0 0 1 2.8-2.8Z" />
    </svg>
  )
}

function ActivityCard({ kind, active }: { kind: ActivityKind; active: boolean }) {
  const data = activity[kind]
  const weeks = useMemo(() => buildCalendar(kind), [kind])
  const months = useMemo(() => monthMarkers(weeks), [weeks])
  const isCodex = kind === 'codex'
  const unit = isCodex ? 'tokens processed' : 'contributions'
  const peakUnit = isCodex ? 'tokens' : 'contributions'

  return (
    <article
      className={`activity-card activity-card--${kind} ${active ? 'is-active' : 'is-behind'}`}
      aria-hidden={!active}
    >
      <header className="activity-card-header">
        <div className="activity-card-identity">
          <span className="activity-card-mark">{isCodex ? <CodexMark /> : <GitHubMark />}</span>
          <div>
            <p>{isCodex ? 'Codex' : 'GitHub'} activity</p>
            <span>Last 12 months</span>
          </div>
        </div>
        <span className="activity-live"><i /> Updated daily</span>
      </header>

      <div className="activity-total">
        <strong>{formatNumber(data.total)}</strong>
        <span>{unit}</span>
      </div>

      <div className="activity-calendar" role="img" aria-label={`${data.total.toLocaleString()} ${unit} across ${data.activeDays} active days in the last year`}>
        <div className="activity-months" aria-hidden="true">
          {months.map((month) => (
            <span key={`${month.week}-${month.label}`} style={{ gridColumnStart: month.week }}>{month.label}</span>
          ))}
        </div>
        <div className="activity-weekdays" aria-hidden="true"><span>Mon</span><span>Wed</span><span>Fri</span></div>
        <div className="activity-grid" aria-hidden="true">
          {weeks.flat().map((day) => (
            <span
              className={`activity-cell level-${day.level} ${day.isFuture ? 'is-future' : ''}`}
              key={day.date}
              title={`${formatDate(day.date)}: ${day.count.toLocaleString()} ${isCodex ? 'tokens' : 'contributions'}`}
            />
          ))}
        </div>
      </div>

      <footer className="activity-card-footer">
        <span><strong>{data.activeDays}</strong> active days</span>
        {data.peak && (
          <span>Peak <strong>{formatNumber(data.peak.count)}</strong> {peakUnit} · {formatDate(data.peak.date)}</span>
        )}
      </footer>
    </article>
  )
}

export function ActivityDeck() {
  const [active, setActive] = useState<ActivityKind>('codex')

  return (
    <aside className="activity-deck" aria-label="Coding activity">
      <div className="activity-switch" aria-label="Choose activity source">
        <span className={`activity-switch-glider is-${active}`} aria-hidden="true" />
        <button type="button" aria-pressed={active === 'codex'} onClick={() => setActive('codex')}>
          Codex
        </button>
        <button type="button" aria-pressed={active === 'github'} onClick={() => setActive('github')}>
          GitHub
        </button>
      </div>

      <div className="activity-card-stack">
        <ActivityCard kind="codex" active={active === 'codex'} />
        <ActivityCard kind="github" active={active === 'github'} />
      </div>

      <p className="activity-caption">
        <span aria-hidden="true">↻</span> A living record of work, refreshed every day.
      </p>
    </aside>
  )
}
