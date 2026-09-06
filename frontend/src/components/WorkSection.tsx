import { type CSSProperties, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import projectsData from '../data/projects.json'
import { ProjectDetail } from './ProjectDetail'
import { ProjectRevolver } from './ProjectRevolver'
import type { ProjectItem } from './projectTypes'
import { ExperienceTimeline } from './ExperienceTimeline'
import { projectPointerPosition } from '../lib/revolver'

const projectItems = projectsData as readonly ProjectItem[]
const projectDates = projectItems.map((project) => project.date)

type WorkSectionProps = {
  onNavigate: (path: string) => void
}

export function WorkSection({ onNavigate }: WorkSectionProps) {
  const [activeProjectIndex, setActiveProjectIndex] = useState(1)
  const [projectOpen, setProjectOpen] = useState(false)
  const work = useRef<HTMLElement>(null)
  const updateProjectPointer = useCallback((position: number) => {
    work.current?.style.setProperty('--project-position', String(projectPointerPosition(position, projectDates)))
  }, [])
  const panel = useRef<HTMLElement>(null)
  const interacted = useRef(false)
  const titleOrigin = useRef<{ x: number; y: number; fontSize: number } | null>(null)
  const selectedProject = projectItems[activeProjectIndex] ?? projectItems[0]

  const openProject = () => {
    titleOrigin.current = null
    const heading = panel.current?.querySelector<HTMLElement>('.reel-item[aria-pressed="true"] strong')
    const panelBounds = panel.current?.getBoundingClientRect()
    if (heading && panelBounds) {
      const bounds = heading.getBoundingClientRect()
      titleOrigin.current = { x: bounds.left - panelBounds.left, y: bounds.top - panelBounds.top, fontSize: Number.parseFloat(getComputedStyle(heading).fontSize) }
    }
    interacted.current = true
    setProjectOpen(true)
  }

  useLayoutEffect(() => {
    if (!projectOpen || !titleOrigin.current || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const heading = panel.current?.querySelector<HTMLElement>('#project-focus-title')
    const panelBounds = panel.current?.getBoundingClientRect()
    if (!heading || !panelBounds) return
    const bounds = heading.getBoundingClientRect()
    const origin = titleOrigin.current
    const x = origin.x - (bounds.left - panelBounds.left)
    const y = origin.y - (bounds.top - panelBounds.top)
    const scale = origin.fontSize / Number.parseFloat(getComputedStyle(heading).fontSize)
    // Move the actual detail heading from the selected entry's position.
    const motion = heading.animate([
      { transform: `translate(${x}px, ${y}px) scale(${scale})`, color: '#293d24' },
      { transform: 'translate(0, 0) scale(1)', color: '#282b24' },
    ], { duration: 420, easing: 'cubic-bezier(.22,1,.36,1)' })
    return () => motion.cancel()
  }, [projectOpen])

  useEffect(() => {
    if (!interacted.current) return
    const target = panel.current?.querySelector<HTMLButtonElement>(projectOpen ? '.project-focus-header button' : '.reel-open')
    target?.focus({ preventScroll: true })
    if (projectOpen && window.matchMedia('(max-width: 850px)').matches && (panel.current?.getBoundingClientRect().top ?? 0) < 24) {
      panel.current?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
    }
  }, [projectOpen])

  return (
    <section ref={work} style={{ '--project-position': projectPointerPosition(1, projectDates) } as CSSProperties} className="portfolio-section work-section tactile-work" id="work" aria-labelledby="work-title">
      <div className="split-work-layout">
        <section className="work-mobile-panel experience-panel" aria-labelledby="work-title">
          <header className="split-panel-intro career-intro">
            <h2 id="work-title">Experience</h2>

          </header>
          <ExperienceTimeline project={selectedProject} projectOpen={projectOpen} />
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
                onPositionChange={updateProjectPointer}
                onOpen={openProject}
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
