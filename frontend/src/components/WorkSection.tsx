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
  tags: readonly string[]
  milestone?: boolean
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

const projectItems = projectsData as readonly ProjectItem[]

export function WorkSection() {
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

        <section
          className={`work-mobile-panel projects-panel ${projectOpen ? 'is-project-detail' : ''}`}
          aria-labelledby={projectOpen ? 'project-focus-title' : 'projects-title'}
        >
          {projectOpen ? (
            <ProjectDetail project={selectedProject} onBack={() => setProjectOpen(false)} />
          ) : (
            <>
              <header className="split-panel-intro projects-intro">
                <p className="section-kicker"><span /> Selected builds</p>
                <h2 id="projects-title">Things that<br /><em>made it out.</em></h2>
                <p>Rotate through the chamber, lock in a project, then choose when to open the full case study.</p>
                <a className="view-all-projects" href="#projects">View all projects <span aria-hidden="true">↗</span></a>
              </header>

              <ProjectRevolver
                projects={projectItems}
                activeIndex={activeProjectIndex}
                onChange={setActiveProjectIndex}
                onOpen={() => setProjectOpen(true)}
              />
            </>
          )}
        </section>
      </div>
    </section>
  )
}
