import { useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { experienceItems } from '../data/experience'

const chapters = [experienceItems[2], experienceItems[1], experienceItems[0]]
const labels = ['First production code', 'The foundation', 'Owning the system']

export function ExperienceTimeline() {
  const [active, setActive] = useState(2)
  const buttons = useRef<(HTMLButtonElement | null)[]>([])
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next = index
    if (event.key === 'ArrowRight') next = (index + 1) % chapters.length
    else if (event.key === 'ArrowLeft') next = (index + chapters.length - 1) % chapters.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = chapters.length - 1
    else return
    event.preventDefault(); setActive(next); buttons.current[next]?.focus()
  }
  return (
    <div className="journey">
      <div className="journey-track" role="tablist" aria-label="Career chapters">
        <span className="journey-progress" style={{ width: `${active * 50}%` }} aria-hidden="true" />
        {chapters.map((chapter, index) => (
          <button key={chapter.id} ref={(element) => { buttons.current[index] = element }} type="button" role="tab" id={`chapter-tab-${chapter.id}`} aria-controls={`chapter-${chapter.id}`} aria-selected={active === index} tabIndex={active === index ? 0 : -1} onClick={() => setActive(index)} onKeyDown={(event) => onKeyDown(event, index)}>
            <span className="journey-point" aria-hidden="true" />
            <span className="journey-date">{index === 0 ? '2024' : index === 1 ? '2026' : 'Now'}{index === 2 && <i aria-hidden="true" />}</span>
            <span className="journey-label">{labels[index]}</span>
          </button>
        ))}
      </div>
      <div className="journey-pages">
        {chapters.map((chapter, index) => (
          <article className="journey-page" key={chapter.id} id={`chapter-${chapter.id}`} role="tabpanel" aria-labelledby={`chapter-tab-${chapter.id}`} tabIndex={0} hidden={active !== index}>
            <div className="journey-meta"><span>{chapter.organization}</span><span>{chapter.period}</span></div>
            <h3>{chapter.title}</h3>
            <p className="journey-thesis">{chapter.summary}</p>
            <p className="journey-description">{chapter.detail}</p>
            <dl className="journey-proof">{chapter.proof.map((proof) => <div key={proof.label}><dt>{proof.value}</dt><dd>{proof.label}</dd></div>)}</dl>
            <div className="journey-page-footer"><span>Chapter 0{index + 1} / 03</span><span aria-hidden="true">{index === 2 ? 'Still writing this one ↗' : 'Every chapter builds on the last.'}</span></div>
          </article>
        ))}
      </div>
    </div>
  )
}
