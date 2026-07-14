import { useState } from 'react'

type ExperienceItem = {
  id: string
  date: string
  title: string
  organization: string
  detail: string
  tags: readonly string[]
  milestone?: boolean
}

type ProjectItem = {
  id: string
  number: string
  date: string
  title: string
  eyebrow: string
  summary: string
  detail: string
  tags: readonly string[]
  href: string
  linkLabel: string
  external?: boolean
}

const experienceItems: readonly ExperienceItem[] = [
  {
    id: 'aivid-internship',
    date: 'Sep 2024 → Sep 2025',
    title: 'Full-stack internship',
    organization: 'AIVID Techvision',
    detail: 'Built a notification platform serving more than 1,000 roles a day, Microsoft Graph workflows, analytics APIs handling over 100,000 records daily, and shared React systems.',
    tags: ['React', 'Node.js', 'Elasticsearch'],
  },
  {
    id: 'aivid-fulltime',
    date: 'Sep 2025 → Present',
    title: 'Full-stack engineer',
    organization: 'AIVID Techvision',
    detail: 'Moved into a full-time engineering role, continuing to own production product work across frontend systems, backend services, platform reliability, and developer experience.',
    tags: ['Product engineering', 'Platform', 'Production systems'],
  },
  {
    id: 'graduation',
    date: '2026',
    title: 'Graduated college',
    organization: 'Indus University',
    detail: 'Completed a B.Tech in Computer Engineering with a 9.66/10 CGPA while building and shipping production software.',
    tags: ['Computer Engineering', '9.66 CGPA'],
    milestone: true,
  },
]

const projectItems: readonly ProjectItem[] = [
  {
    id: 'nsk',
    number: '01',
    date: '2025',
    title: 'Nashik Sports Klub',
    eyebrow: 'Live product',
    summary: 'A race-safe booking platform for real sports inventory.',
    detail: 'Built multi-tenant booking for Pickleball and Cricket with temporary holds, MongoDB transactions, role-specific workflows, real-time availability, and AWS deployment. A 500-user concurrency test committed exactly one booking for the final slot.',
    tags: ['React', 'Node.js', 'MongoDB', 'AWS'],
    href: 'https://www.nashiksportsklub.com',
    linkLabel: 'Visit live product',
    external: true,
  },
  {
    id: 'portfolio-rag',
    number: '02',
    date: '2026 → Now',
    title: 'This portfolio + RAG',
    eyebrow: 'Current build',
    summary: 'An inspectable portfolio that can answer for itself.',
    detail: 'Designed trained retrieval routes, streamed answers, model fallback, visible evidence and timing receipts. The system combines a React interface, FastAPI services, PostgreSQL with pgvector, and provider-aware limits.',
    tags: ['React', 'FastAPI', 'pgvector', 'RAG'],
    href: '#playground',
    linkLabel: 'Open the RAG lab',
  },
]

export function WorkSection() {
  const [activeExperience, setActiveExperience] = useState('aivid-fulltime')
  const [activeProject, setActiveProject] = useState('portfolio-rag')
  const selectedExperience = experienceItems.find((item) => item.id === activeExperience) ?? experienceItems[0]
  const selectedProject = projectItems.find((item) => item.id === activeProject) ?? projectItems[0]

  return (
    <section className="portfolio-section work-section" id="work" aria-labelledby="work-title">
      <header className="section-header centered-section-header">
        <p><span>02</span> Experience + projects</p>
      </header>

      <div className="split-work-layout">
        <section className="work-mobile-panel experience-panel" aria-labelledby="work-title">
          <header className="split-panel-intro">
            <p className="section-kicker"><span /> Experience</p>
            <h2 id="work-title">The work,<br /><em>in sequence.</em></h2>
            <p>One company, growing responsibility, and a degree completed along the way.</p>
          </header>

          <div className="experience-stage">
            <nav className="experience-rail" aria-label="Experience timeline">
              {experienceItems.map((item) => (
                <button
                  type="button"
                  className={`experience-stop ${item.id === selectedExperience.id ? 'is-active' : ''} ${item.milestone ? 'is-milestone' : ''}`}
                  key={item.id}
                  aria-pressed={item.id === selectedExperience.id}
                  onMouseEnter={() => setActiveExperience(item.id)}
                  onFocus={() => setActiveExperience(item.id)}
                  onClick={() => setActiveExperience(item.id)}
                >
                  <span className="experience-node" aria-hidden="true" />
                  <time>{item.date}</time>
                  <strong>{item.title}</strong>
                </button>
              ))}
            </nav>

            <article className="experience-detail-card" aria-live="polite">
              <p>{selectedExperience.organization}</p>
              <h3>{selectedExperience.title}</h3>
              <time>{selectedExperience.date}</time>
              <p>{selectedExperience.detail}</p>
              <ul aria-label={`${selectedExperience.title} details`}>
                {selectedExperience.tags.map((tag) => <li key={tag}>{tag}</li>)}
              </ul>
            </article>
          </div>
        </section>

        <section className="work-mobile-panel projects-panel" aria-labelledby="projects-title">
          <header className="split-panel-intro projects-intro">
            <p className="section-kicker"><span /> Selected builds</p>
            <h2 id="projects-title">Things that<br /><em>made it out.</em></h2>
            <p>Two production builds. Select one to see what was actually engineered.</p>
          </header>

          <nav className="project-index" aria-label="Selected projects">
            {projectItems.map((project) => (
              <button
                type="button"
                className={`project-index-row ${project.id === selectedProject.id ? 'is-active' : ''}`}
                key={project.id}
                aria-pressed={project.id === selectedProject.id}
                onMouseEnter={() => setActiveProject(project.id)}
                onFocus={() => setActiveProject(project.id)}
                onClick={() => setActiveProject(project.id)}
              >
                <span>{project.number}</span>
                <span>
                  <time>{project.date}</time>
                  <strong>{project.title}</strong>
                  <small>{project.summary}</small>
                </span>
                <span aria-hidden="true">↗</span>
              </button>
            ))}
          </nav>

          <article className="project-detail-card" aria-live="polite">
            <header>
              <p>{selectedProject.eyebrow}</p>
              <h3>{selectedProject.title}</h3>
            </header>
            <p>{selectedProject.detail}</p>
            <footer>
              <ul aria-label={`${selectedProject.title} technologies`}>
                {selectedProject.tags.map((tag) => <li key={tag}>{tag}</li>)}
              </ul>
              <a
                href={selectedProject.href}
                target={selectedProject.external ? '_blank' : undefined}
                rel={selectedProject.external ? 'noreferrer' : undefined}
              >
                {selectedProject.linkLabel} <span aria-hidden="true">↗</span>
              </a>
            </footer>
          </article>
        </section>
      </div>
    </section>
  )
}
