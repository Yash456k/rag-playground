import { useState } from 'react'
import { experienceItems } from '../data/experience'

export function ExperienceTimeline() {
  const [activeId, setActiveId] = useState(experienceItems[0].id)

  return (
    <div className="career-timeline" aria-label="Experience timeline">
      {experienceItems.map((item) => {
        const expanded = activeId === item.id
        return (
          <article className={`career-entry ${expanded ? 'is-expanded' : ''} ${item.current ? 'is-current' : ''}`} key={item.id}>
            <div className="career-axis" aria-hidden="true">
              <span className="career-year">{item.year}</span>
              <span className="career-dot" />
            </div>
            <div className="career-content">
              <h3 className="career-heading">
                <button
                  type="button"
                  id={`career-trigger-${item.id}`}
                  aria-expanded={expanded}
                  aria-controls={`career-panel-${item.id}`}
                  onClick={() => setActiveId(item.id)}
                >
                  <span className="career-heading-copy">
                    <span className="career-organization">{item.organization}{item.current && <span className="career-current">Now</span>}</span>
                    <span className="career-title">{item.title}</span>
                    <span className="career-period">{item.period}</span>
                  </span>
                  <span className="career-toggle" aria-hidden="true">{expanded ? '−' : '+'}</span>
                </button>
              </h3>
              <div
                className="career-expansion"
                id={`career-panel-${item.id}`}
                role="region"
                aria-labelledby={`career-trigger-${item.id}`}
                aria-hidden={!expanded}
                inert={!expanded}
              >
                <div className="career-expansion-inner">
                  <div className="career-story">
                    <p className="career-chapter">{item.label}</p>
                    <p className="career-summary">{item.summary}</p>
                    <p className="career-detail">{item.detail}</p>
                    <dl className="career-proof">
                      {item.proof.map((proof) => (
                        <div key={proof.label}><dt>{proof.value}</dt><dd>{proof.label}</dd></div>
                      ))}
                    </dl>
                  </div>
                </div>
              </div>
            </div>
          </article>
        )
      })}
    </div>
  )
}
