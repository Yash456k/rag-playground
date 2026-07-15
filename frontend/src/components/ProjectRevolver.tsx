import { useEffect, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import type { ProjectItem } from './projectTypes'

type ProjectRevolverProps = {
  projects: readonly ProjectItem[]
  activeIndex: number
  onChange: (index: number) => void
  onOpen: () => void
}

function wrapIndex(index: number, length: number) {
  return (index + length) % length
}

function circularOffset(index: number, activeIndex: number, length: number) {
  let offset = index - activeIndex
  const halfway = Math.floor(length / 2)
  if (offset > halfway) offset -= length
  if (offset < -halfway) offset += length
  return offset
}

function slotName(offset: number) {
  if (offset === -1) return 'previous'
  if (offset === 0) return 'active'
  if (offset === 1) return 'next'
  return 'hidden'
}

export function ProjectRevolver({ projects, activeIndex, onChange, onOpen }: ProjectRevolverProps) {
  const wheelLock = useRef<number | null>(null)
  const revolverRef = useRef<HTMLDivElement>(null)
  const selectedProject = projects[activeIndex] ?? projects[0]

  useEffect(() => () => {
    if (wheelLock.current !== null) window.clearTimeout(wheelLock.current)
  }, [])

  const rotate = (direction: -1 | 1) => {
    onChange(wrapIndex(activeIndex + direction, projects.length))
  }

  useEffect(() => {
    const revolver = revolverRef.current
    if (!revolver) return

    const handleWheel = (event: globalThis.WheelEvent) => {
      event.preventDefault()
      event.stopPropagation()
      if (Math.abs(event.deltaY) < 8 || wheelLock.current !== null) return

      const direction = event.deltaY > 0 ? 1 : -1
      onChange(wrapIndex(activeIndex + direction, projects.length))
      wheelLock.current = window.setTimeout(() => {
        wheelLock.current = null
      }, 150)
    }

    revolver.addEventListener('wheel', handleWheel, { passive: false })
    return () => revolver.removeEventListener('wheel', handleWheel)
  }, [activeIndex, onChange, projects.length])

  const handleKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    event.preventDefault()
    rotate(event.key === 'ArrowDown' ? 1 : -1)
  }

  return (
    <div className="project-revolver-stage">
      <div
        ref={revolverRef}
        className="project-revolver"
        role="group"
        aria-label="Project selector"
        tabIndex={0}
        onKeyDown={handleKeyboard}
      >
        <button className="revolver-step is-up" type="button" onClick={() => rotate(-1)} aria-label="Previous project">
          <span aria-hidden="true">↑</span> Previous
        </button>

        <div className="project-revolver-viewport">
          {projects.map((project, index) => {
            const offset = circularOffset(index, activeIndex, projects.length)
            const slot = slotName(offset)
            return (
              <button
                className="project-revolver-item"
                data-slot={slot}
                type="button"
                key={project.id}
                tabIndex={slot === 'hidden' ? -1 : 0}
                aria-pressed={slot === 'active'}
                aria-label={`${slot === 'active' ? 'Selected project' : 'Select project'}: ${project.title}`}
                onClick={() => onChange(index)}
              >
                <span>{project.number}</span>
                <span>
                  <time>{project.date}</time>
                  <strong>{project.title}</strong>
                  <small>{project.summary}</small>
                </span>
              </button>
            )
          })}
        </div>

        <button className="revolver-step is-down" type="button" onClick={() => rotate(1)} aria-label="Next project">
          Next <span aria-hidden="true">↓</span>
        </button>
      </div>

      <div className="project-selection-receipt" aria-live="polite">
        <button type="button" onClick={onOpen} aria-label={`View ${selectedProject.title}`}>
          View
          <span className="project-action-window">
            <span className="project-action-name" key={selectedProject.id}>{selectedProject.title}</span>
          </span>
          <span aria-hidden="true">↗</span>
        </button>
      </div>
    </div>
  )
}
