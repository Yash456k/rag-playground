import { useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent } from 'react'
import { springStep, wrapIndex } from '../lib/revolver'
import type { ProjectItem } from './projectTypes'

type ProjectRevolverProps = {
  projects: readonly ProjectItem[]
  activeIndex: number
  onChange: (index: number) => void
  onOpen: () => void
}

export function ProjectRevolver({ projects, activeIndex, onChange, onOpen }: ProjectRevolverProps) {
  const [position, setPosition] = useState(activeIndex)
  const physical = useRef({ position: activeIndex, velocity: 0, target: activeIndex })
  const frame = useRef<number | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const gesture = useRef<{ start: number; origin: number; dragged: boolean; touch: boolean } | null>(null)
  const suppressClick = useRef(false)
  const selectedProject = projects[activeIndex] ?? projects[0]

  const animate = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current)
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      physical.current.position = physical.current.target
      physical.current.velocity = 0
      setPosition(physical.current.target)
      frame.current = null
      return
    }
    let previous = performance.now()
    const tick = (now: number) => {
      const state = physical.current
      const next = springStep(state.position, state.velocity, state.target, Math.min((now - previous) / 1000, .064))
      previous = now
      state.position = next.position
      state.velocity = next.velocity
      if (Math.abs(state.position - state.target) < .0005 && Math.abs(state.velocity) < .005) {
        state.position = state.target
        state.velocity = 0
        setPosition(state.target)
        frame.current = null
      } else {
        setPosition(state.position)
        frame.current = requestAnimationFrame(tick)
      }
    }
    frame.current = requestAnimationFrame(tick)
  }, [])

  useEffect(() => () => { if (frame.current !== null) cancelAnimationFrame(frame.current) }, [])

  const select = useCallback((target: number) => {
    physical.current.target = target
    onChange(wrapIndex(target, projects.length))
    animate()
  }, [animate, onChange, projects.length])

  const rotate = useCallback((direction: number) => {
    // Bound queued travel without throwing away input during an animation.
    const state = physical.current
    const target = state.target + direction
    select(Math.max(Math.round(state.position) - 3, Math.min(Math.round(state.position) + 3, target)))
  }, [select])

  useEffect(() => {
    const element = root.current
    if (!element) return
    let accumulated = 0
    let lastInput = 0
    let lastStep = 0
    const wheel = (event: WheelEvent) => {
      if (event.ctrlKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return
      event.preventDefault()
      const now = performance.now()
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 300 : 1)
      if (now - lastInput > 160 || Math.sign(accumulated) !== Math.sign(delta)) accumulated = 0
      lastInput = now
      accumulated += delta
      if (Math.abs(accumulated) >= 45 && now - lastStep > 130) {
        rotate(Math.sign(accumulated))
        accumulated = 0
        lastStep = now
      }
    }
    element.addEventListener('wheel', wheel, { passive: false })
    return () => element.removeEventListener('wheel', wheel)
  }, [rotate])

  const keyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    event.preventDefault()
    rotate(event.key === 'ArrowDown' ? 1 : -1)
  }
  const pointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    suppressClick.current = false
    gesture.current = { start: event.pointerType === 'touch' ? event.clientX : event.clientY, origin: physical.current.position, dragged: false, touch: event.pointerType === 'touch' }
  }
  const pointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const drag = gesture.current
    if (!drag) return
    const delta = (drag.touch ? event.clientX : event.clientY) - drag.start
    if (!drag.dragged && Math.abs(delta) < 8) return
    drag.dragged = true
    suppressClick.current = true
    event.currentTarget.setPointerCapture(event.pointerId)
    if (frame.current !== null) cancelAnimationFrame(frame.current)
    frame.current = null
    const spacing = Number.parseFloat(getComputedStyle(event.currentTarget).getPropertyValue('--reel-spacing')) || 104
    physical.current.position = drag.origin - delta / spacing
    physical.current.velocity = 0
    setPosition(physical.current.position)
  }
  const pointerEnd = (event: PointerEvent<HTMLDivElement>) => {
    const drag = gesture.current
    gesture.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    if (drag?.dragged) select(Math.round(physical.current.position))
  }
  const center = Math.round(position)

  return (
    <div className="smooth-reel-stage">
      <div ref={root} className="smooth-reel" role="group" aria-label="Project selector" tabIndex={0} onKeyDown={keyboard}>
        <div className="reel-aperture" onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerEnd} onPointerCancel={pointerEnd}>
          {[-2, -1, 0, 1, 2].map((slot) => {
            const absolute = center + slot
            const index = wrapIndex(absolute, projects.length)
            const project = projects[index]
            const offset = absolute - position
            const distance = Math.abs(offset)
            const opacity = distance <= 1 ? 1 - distance * .55 : Math.max(0, .45 * (2 - distance))
            return (
              <button type="button" className="reel-item" key={absolute}
                style={{ '--offset': offset, opacity, transform: `translateY(calc(-50% + ${offset} * var(--reel-spacing))) perspective(900px) rotateX(${offset * -13}deg) scale(${1 - Math.min(distance, 2) * .055})` } as CSSProperties}
                aria-hidden={Math.abs(slot) > 1} tabIndex={Math.abs(slot) > 1 ? -1 : 0}
                aria-pressed={index === activeIndex && Math.abs(slot) <= 1}
                aria-label={`${index === activeIndex ? 'Selected project' : 'Select project'}: ${project.title}`}
                onClick={(event) => { if (event.detail === 0 || !suppressClick.current) select(absolute) }}>
                <span className="reel-number">{project.number}</span>
                <span><strong>{project.title}</strong><small>{project.summary}</small></span>
              </button>
            )
          })}
        </div>
        <div className="reel-navigation"><button type="button" aria-label="Previous project" onClick={() => rotate(-1)}>↑</button><button type="button" aria-label="Next project" onClick={() => rotate(1)}>↓</button></div>
      </div>
      <p className="reel-summary">{selectedProject.summary}</p>
      <div className="reel-footer">
        <span className="reel-hint"><span className="desktop-reel-hint">Scroll or drag to explore</span><span className="mobile-reel-hint">Swipe sideways to explore</span></span>
        <button type="button" className="reel-open" onClick={onOpen} aria-label={`View ${selectedProject.title}`}>View project <span aria-hidden="true">↗</span></button>
      </div>
      <span className="visually-hidden" aria-live="polite">Selected: {selectedProject.title}</span>
    </div>
  )
}
