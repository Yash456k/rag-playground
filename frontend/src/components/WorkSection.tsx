import { useState } from 'react'
import projectsData from '../data/projects.json'
import { ProjectDetail } from './ProjectDetail'
import { ProjectRevolver } from './ProjectRevolver'
import type { ProjectItem } from './projectTypes'
import { ExperienceTimeline } from './ExperienceTimeline'

const projectItems = projectsData as readonly ProjectItem[]

type WorkSectionProps = {
  onNavigate: (path: string) => void
}

export function WorkSection({ onNavigate }: WorkSectionProps) {
  const [activeProjectIndex, setActiveProjectIndex] = useState(1)
  const [projectOpen, setProjectOpen] = useState(false)
  const selectedProject = projectItems[activeProjectIndex] ?? projectItems[0]

  return (
    <section className="portfolio-section work-section" id="work" aria-labelledby="work-title">
      <header className="section-header centered-section-header">
        <p><span>02</span> Experience + projects</p>
      </header>

      <div className="split-work-layout">
        <section className="work-mobile-panel experience-panel" aria-labelledby="work-title">
          <header className="split-panel-intro career-intro">
            <p className="work-overline"><span>01 / The journey</span><span>2024 — Today</span></p>
            <h2 id="work-title">Experience<span className="heading-period">.</span></h2>
            <p className="work-subtitle">A little more responsibility. Every chapter.</p>
          </header>
          <ExperienceTimeline />
        </section>

        <section
          className={`work-mobile-panel projects-panel ${projectOpen ? 'is-project-detail' : ''}`}
          aria-labelledby={projectOpen ? 'project-focus-title' : 'projects-title'}
        >
          <div className={`project-view-stack ${projectOpen ? 'is-detail-open' : ''}`}>
            <div className="project-selector-view" aria-hidden={projectOpen} inert={projectOpen}>
              <header className="split-panel-intro projects-intro">
                <p className="work-overline"><span>02 / Selected work</span><span>0{projectItems.length} projects</span></p>
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
            <div className="project-detail-view" aria-hidden={!projectOpen} inert={!projectOpen}>
              <ProjectDetail project={selectedProject} onBack={() => setProjectOpen(false)} />
            </div>
          </div>
        </section>
      </div>
    </section>
  )
}
