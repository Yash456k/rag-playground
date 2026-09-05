import { useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent } from 'react'
import { experienceItems } from '../data/experience'
import { wrapIndex } from '../lib/revolver'

const chapters = [experienceItems[2], experienceItems[1], experienceItems[0]]
const labels = ['2024', '2026', 'Now']

export function ExperienceTimeline() {
  const [active, setActive] = useState(2)
  const buttons = useRef<(HTMLButtonElement | null)[]>([])
  const touchStart = useRef<number | null>(null)
  const select = (index: number) => setActive(wrapIndex(index, chapters.length))
  const keyboard = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next = index
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = wrapIndex(index + 1, chapters.length)
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = wrapIndex(index - 1, chapters.length)
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = chapters.length - 1
    else return
    event.preventDefault()
    setActive(next)
    buttons.current[next]?.focus()
  }
  return (
    <div className="career-deck">
      <div className="career-dates" role="tablist" aria-label="Experience timeline">
        {chapters.map((chapter, index) => <button key={chapter.id} ref={(element) => { buttons.current[index] = element }} type="button" role="tab" id={`career-tab-${chapter.id}`} aria-controls={`career-${chapter.id}`} aria-selected={active === index} tabIndex={active === index ? 0 : -1} onClick={() => select(index)} onKeyDown={(event) => keyboard(event, index)}><span aria-hidden="true" />{labels[index]}</button>)}
      </div>
      <div className="career-stack" onTouchStart={(event) => { touchStart.current = event.touches[0].clientX }} onTouchEnd={(event) => { if (touchStart.current !== null) { const distance = event.changedTouches[0].clientX - touchStart.current; if (Math.abs(distance) > 40) select(active + (distance < 0 ? 1 : -1)); touchStart.current = null } }} onTouchCancel={() => { touchStart.current = null }}>
        {chapters.map((chapter, index) => {
          const depth = wrapIndex(index - active, chapters.length)
          return <article className={`career-card ${depth === 0 ? 'is-current' : ''}`} key={chapter.id} style={{ '--depth': depth, zIndex: chapters.length - depth } as CSSProperties} id={`career-${chapter.id}`} role="tabpanel" aria-labelledby={`career-tab-${chapter.id}`} aria-hidden={depth !== 0} inert={depth !== 0} tabIndex={depth === 0 ? 0 : -1}>
            <div className="career-card-content">
              <div className="career-card-meta"><span>{chapter.organization}</span>{chapter.current && <span className="career-current">Current</span>}</div>
              <h3>{chapter.title}</h3><time>{chapter.period}</time>
              <p>{chapter.detail}</p>
              {index !== 2 && <div className="career-proof">{index === 1 ? '9.66 / 10 CGPA' : '100K+ analytics records · 1,000+ roles / day'}</div>}
            </div>
          </article>
        })}
      </div>
      <div className="career-navigation"><span>{String(active + 1).padStart(2, '0')} <i>/ 03</i></span><div><button type="button" onClick={() => select(active - 1)} aria-label="Previous experience">←</button><button type="button" onClick={() => select(active + 1)} aria-label="Next experience">→</button></div></div>
    </div>
  )
}
