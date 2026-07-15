import { useCallback, useEffect, useRef, useState } from 'react'
import type { AnimationEvent, KeyboardEvent } from 'react'
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

const revolverSlots = [-2, -1, 0, 1, 2] as const

function slotName(offset: (typeof revolverSlots)[number]) {
  if (offset === -2) return 'far-previous'
  if (offset === -1) return 'previous'
  if (offset === 0) return 'active'
  if (offset === 1) return 'next'
  return 'far-next'
}

export function ProjectRevolver({ projects, activeIndex, onChange, onOpen }: ProjectRevolverProps) {
  const motionTimer = useRef<number | null>(null)
  const motionLock = useRef(false)
  const pendingDirection = useRef<-1 | 1 | null>(null)
  const revolverRef = useRef<HTMLDivElement>(null)
  const [motion, setMotion] = useState<-1 | 1 | null>(null)
  const selectedProject = projects[activeIndex] ?? projects[0]

  useEffect(() => () => {
    if (motionTimer.current !== null) window.clearTimeout(motionTimer.current)
  }, [])

  const completeRotation = useCallback(() => {
    const direction = pendingDirection.current
    if (direction === null) return

    if (motionTimer.current !== null) window.clearTimeout(motionTimer.current)
    pendingDirection.current = null
    motionTimer.current = null
    onChange(wrapIndex(activeIndex + direction, projects.length))
    setMotion(null)
    motionLock.current = false
  }, [activeIndex, onChange, projects.length])

  const rotate = useCallback((direction: -1 | 1) => {
    if (motionLock.current || projects.length < 2) return

    motionLock.current = true
    pendingDirection.current = direction
    setMotion(direction)
    motionTimer.current = window.setTimeout(completeRotation, 380)
  }, [completeRotation, projects.length])

  const handleAnimationEnd = (event: AnimationEvent<HTMLDivElement>) => {
    const target = event.target
    if (!(target instanceof HTMLElement) || target.dataset.slot !== 'active') return
    if (!event.animationName.startsWith('revolver-roll-')) return
    completeRotation()
  }

  useEffect(() => {
    const revolver = revolverRef.current
    if (!revolver) return

    const handleWheel = (event: globalThis.WheelEvent) => {
      event.preventDefault()
      event.stopPropagation()
      if (Math.abs(event.deltaY) < 8) return

      const direction = event.deltaY > 0 ? 1 : -1
      rotate(direction)
    }

    revolver.addEventListener('wheel', handleWheel, { passive: false })
    return () => revolver.removeEventListener('wheel', handleWheel)
  }, [rotate])

  const handleKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    event.preventDefault()
    rotate(event.key === 'ArrowDown' ? 1 : -1)
  }

  return (
    <div className="project-revolver-stage">
      <div
        ref={revolverRef}
        className={`project-revolver ${motion === 1 ? 'is-rolling-next' : motion === -1 ? 'is-rolling-previous' : ''}`}
        role="group"
        aria-label="Project selector"
        tabIndex={0}
        onKeyDown={handleKeyboard}
        onAnimationEnd={handleAnimationEnd}
      >
        <button className="revolver-step is-up" type="button" onClick={() => rotate(-1)} aria-label="Previous project">
          <span aria-hidden="true">↑</span> Previous
        </button>

        <div className="project-revolver-viewport">
          {revolverSlots.map((offset) => {
            const index = wrapIndex(activeIndex + offset, projects.length)
            const project = projects[index]
            const slot = slotName(offset)
            return (
              <button
                className="project-revolver-item"
                data-slot={slot}
                type="button"
                key={offset}
                tabIndex={Math.abs(offset) > 1 ? -1 : 0}
                aria-hidden={Math.abs(offset) > 1}
                aria-pressed={slot === 'active'}
                aria-label={`${slot === 'active' ? 'Selected project' : 'Select project'}: ${project.title}`}
                onClick={() => {
                  if (offset === -1) rotate(-1)
                  if (offset === 1) rotate(1)
                }}
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
