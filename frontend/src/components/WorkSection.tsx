import { useState } from 'react'
import projectsData from '../data/projects.json'
import { ProjectDetail } from './ProjectDetail'
import { ProjectRevolver } from './ProjectRevolver'
import type { ProjectItem } from './projectTypes'

type ExperienceItem = {
  id: string
  date: string
  title: string
  organization: string
  detail: string
  milestone?: boolean
}

const experienceItems: readonly ExperienceItem[] = [
  {
    id: 'aivid-internship',
    date: 'Sep 2024 → Sep 2025',
    title: 'Full-stack internship',
    organization: 'AIVID Techvision',
    detail: 'Built a notification platform serving more than 1,000 roles a day, Microsoft Graph workflows, analytics APIs handling over 100,000 records daily, and shared React systems.',
  },
  {
    id: 'aivid-fulltime',
    date: 'Sep 2025 → Present',
    title: 'Full-stack engineer',
    organization: 'AIVID Techvision',
    detail: 'Moved into a full-time engineering role, continuing to own production product work across frontend systems, backend services, platform reliability, and developer experience.',
  },
  {
    id: 'graduation',
    date: '2026',
    title: 'Graduated college',
    organization: 'Indus University',
    detail: 'Completed a B.Tech in Computer Engineering with a 9.66/10 CGPA while building and shipping production software.',
    milestone: true,
  },
]

const projectItems = projectsData as readonly ProjectItem[]

type WorkSectionProps = {
  onNavigate: (path: string) => void
}

export function WorkSection({ onNavigate }: WorkSectionProps) {
  const [activeExperience, setActiveExperience] = useState('aivid-fulltime')
  const [activeProjectIndex, setActiveProjectIndex] = useState(1)
  const [projectOpen, setProjectOpen] = useState(false)
  const selectedExperience = experienceItems.find((item) => item.id === activeExperience) ?? experienceItems[0]
  const selectedProject = projectItems[activeProjectIndex] ?? projectItems[0]

  return (
    <section className="portfolio-section work-section" id="work" aria-labelledby="work-title">
      <header className="section-header centered-section-header">
        <p><span>02</span> Experience + projects</p>
      </header>

      <div className="split-work-layout">
        <section className="work-mobile-panel experience-panel" aria-labelledby="work-title">
          <header className="split-panel-intro">
            <h2 id="work-title">Experience</h2>
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
            </article>
          </div>
        </section>

        <section
          className={`work-mobile-panel projects-panel ${projectOpen ? 'is-project-detail' : ''}`}
          aria-labelledby={projectOpen ? 'project-focus-title' : 'projects-title'}
        >
          <div className={`project-view-stack ${projectOpen ? 'is-detail-open' : ''}`}>
            <div className="project-selector-view" aria-hidden={projectOpen}>
              <header className="split-panel-intro projects-intro">
                <h2 id="projects-title">Things that<br /><em>made it out.</em></h2>
                <a
                  className="view-all-projects"
                  href="/projects"
                  onClick={(event) => { event.preventDefault(); onNavigate('/projects') }}
                >
                  View all projects <span aria-hidden="true">↗</span>
                </a>
              </header>

              <ProjectRevolver
                projects={projectItems}
                activeIndex={activeProjectIndex}
                onChange={setActiveProjectIndex}
                onOpen={() => setProjectOpen(true)}
              />
            </div>
            <div className="project-detail-view" aria-hidden={!projectOpen}>
              <ProjectDetail project={selectedProject} onBack={() => setProjectOpen(false)} />
            </div>
          </div>
        </section>
      </div>
    </section>
  )
}
