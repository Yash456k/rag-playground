import { useEffect, useRef, useState } from 'react'
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
  const panel = useRef<HTMLElement>(null)
  const interacted = useRef(false)
  const selectedProject = projectItems[activeProjectIndex] ?? projectItems[0]

  useEffect(() => {
    if (!interacted.current) return
    const target = panel.current?.querySelector<HTMLButtonElement>(projectOpen ? '.project-focus-header button' : '.reel-open')
    target?.focus({ preventScroll: true })
    if (projectOpen) panel.current?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
  }, [projectOpen])

  return (
    <section className="portfolio-section work-section tactile-work" id="work" aria-labelledby="work-title">
      <div className="split-work-layout">
        <section className="work-mobile-panel experience-panel" aria-labelledby="work-title">
          <header className="split-panel-intro career-intro">
            <h2 id="work-title">Experience</h2>

          </header>
          <ExperienceTimeline />
        </section>

        <section
          ref={panel}
          className={`work-mobile-panel projects-panel ${projectOpen ? 'is-project-detail' : ''}`}
          aria-labelledby={projectOpen ? 'project-focus-title' : 'projects-title'}
        >
          <div className={`project-view-stack ${projectOpen ? 'is-detail-open' : ''}`}>
            <div className="project-selector-view" aria-hidden={projectOpen} inert={projectOpen}>
              <header className="split-panel-intro projects-intro">
                <h2 id="projects-title">Projects</h2>
                <a
                  className="view-all-projects"
                  href="/projects"
                  onClick={(event) => { event.preventDefault(); onNavigate('/projects') }}
                >
                  All projects <span aria-hidden="true">↗</span>
                </a>
              </header>

              <ProjectRevolver
                projects={projectItems}
                activeIndex={activeProjectIndex}
                onChange={setActiveProjectIndex}
                onOpen={() => { interacted.current = true; setProjectOpen(true) }}
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
