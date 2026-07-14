import { useState } from 'react'

type TimelineEvent = {
  id: string
  date: string
  title: string
  eyebrow: string
  detail: string
  tags: readonly string[]
  position: number
  href?: string
  linkLabel?: string
  milestone?: boolean
}

const experienceEvents: readonly TimelineEvent[] = [
  {
    id: 'aivid-internship',
    date: 'Sep 2024',
    title: 'Full-stack internship',
    eyebrow: 'AIVID Techvision',
    detail: 'Built multi-tenant notifications, Microsoft Graph workflows, analytics APIs, dashboards, and shared React systems.',
    tags: ['React', 'Node.js', 'Elasticsearch'],
    position: 15,
  },
  {
    id: 'aivid-fulltime',
    date: 'Sep 2025 → Present',
    title: 'Full-stack engineer',
    eyebrow: 'AIVID Techvision',
    detail: 'Moved into a full-time engineering role and continued shipping production product and platform work.',
    tags: ['Product engineering', 'Platform work'],
    position: 55,
  },
  {
    id: 'graduation',
    date: '2026',
    title: 'Graduated college',
    eyebrow: 'Indus University',
    detail: 'Completed a B.Tech in Computer Engineering after maintaining a 9.66/10 CGPA while building production software.',
    tags: ['Computer Engineering', '9.66 CGPA'],
    position: 88,
    milestone: true,
  },
]

const projectEvents: readonly TimelineEvent[] = [
  {
    id: 'nsk',
    date: '2025',
    title: 'Nashik Sports Klub',
    eyebrow: 'Production booking platform',
    detail: 'Built race-safe booking, role-specific workflows, live inventory, automated delivery, and AWS production infrastructure.',
    tags: ['MERN', 'Transactions', 'AWS'],
    position: 32,
    href: 'https://www.nashiksportsklub.com',
    linkLabel: 'Visit live product',
  },
  {
    id: 'portfolio-rag',
    date: '2026 → Now',
    title: 'This portfolio + RAG',
    eyebrow: 'Current build',
    detail: 'Designed an inspectable portfolio with trained retrieval routes, streamed answers, provider fallback, and visible evidence.',
    tags: ['React', 'FastAPI', 'pgvector'],
    position: 79,
    href: '#playground',
    linkLabel: 'Open the RAG lab',
  },
]

function TimelineLane({
  label,
  events,
  activeId,
  onSelect,
}: {
  label: string
  events: readonly TimelineEvent[]
  activeId: string
  onSelect: (id: string) => void
}) {
  const activeEvent = events.find((event) => event.id === activeId) ?? events[0]

  return (
    <section className="timeline-lane" aria-label={`${label} timeline`}>
      <header className="timeline-lane-heading">
        <h3>{label}</h3>
        <span>Hover or focus a point</span>
      </header>

      <div className="timeline-track" role="group" aria-label={`${label} milestones`}>
        <span className="timeline-axis-label is-start" aria-hidden="true">2024</span>
        <span className="timeline-axis-label is-end" aria-hidden="true">2026</span>
        {events.map((event) => (
          <button
            className={`timeline-node ${event.id === activeEvent.id ? 'is-active' : ''} ${event.milestone ? 'is-milestone' : ''}`}
            type="button"
            key={event.id}
            style={{ left: `${event.position}%` }}
            aria-pressed={event.id === activeEvent.id}
            onMouseEnter={() => onSelect(event.id)}
            onFocus={() => onSelect(event.id)}
            onClick={() => onSelect(event.id)}
          >
            <span className="timeline-dot" aria-hidden="true" />
            <time>{event.date}</time>
            <strong>{event.title}</strong>
          </button>
        ))}
      </div>

      <article className="timeline-detail" aria-live="polite">
        <div>
          <span>{activeEvent.eyebrow}</span>
          <h4>{activeEvent.title}</h4>
        </div>
        <p>{activeEvent.detail}</p>
        <footer>
          <ul aria-label={`${activeEvent.title} technologies and details`}>
            {activeEvent.tags.map((tag) => <li key={tag}>{tag}</li>)}
          </ul>
          {activeEvent.href && (
            <a
              href={activeEvent.href}
              target={activeEvent.href.startsWith('http') ? '_blank' : undefined}
              rel={activeEvent.href.startsWith('http') ? 'noreferrer' : undefined}
            >
              {activeEvent.linkLabel} <span aria-hidden="true">↗</span>
            </a>
          )}
        </footer>
      </article>
    </section>
  )
}

export function WorkSection() {
  const [activeExperience, setActiveExperience] = useState('aivid-fulltime')
  const [activeProject, setActiveProject] = useState('portfolio-rag')

  return (
    <section className="portfolio-section work-section" id="work" aria-labelledby="work-title">
      <header className="section-header centered-section-header">
        <p><span>02</span> Experience + projects</p>
      </header>

      <div className="journey-layout">
        <header className="journey-intro">
          <div>
            <p className="section-kicker"><span /> Built over time</p>
            <h2 id="work-title">The work,<br /><em>in sequence.</em></h2>
          </div>
          <p>
            Two tracks for the roles and projects that shaped how I build. Move across a point to inspect the work behind it.
          </p>
        </header>

        <div className="timeline-board">
          <TimelineLane
            label="Experience"
            events={experienceEvents}
            activeId={activeExperience}
            onSelect={setActiveExperience}
          />
          <TimelineLane
            label="Projects"
            events={projectEvents}
            activeId={activeProject}
            onSelect={setActiveProject}
          />
        </div>
      </div>
    </section>
  )
}
