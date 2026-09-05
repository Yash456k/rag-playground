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
        <p><span>02 /</span> A practice in building</p><a href="#playground">Meet the AI behind this site ↗</a>
      </header>

      <div className="split-work-layout">
        <section className="work-mobile-panel experience-panel" aria-labelledby="work-title">
          <header className="split-panel-intro career-intro">
            <p className="work-overline"><span>The experience</span><span>01 — 03</span></p>
            <h2 id="work-title">A little further.<br /><em>Every chapter.</em></h2>
            
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
                <p className="work-overline"><span>Selected projects</span><span>0{projectItems.length} in the collection</span></p>
                <h2 id="projects-title">Built to be<br /><em>used.</em></h2>
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
