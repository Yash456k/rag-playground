import { describe, expect, it } from 'vitest'
import { cardSwipeDirection, projectDatePosition, projectPointerPosition, springStep, wrapIndex } from './revolver'

describe('continuous project rotation', () => {
  it('wraps repeated travel in either direction', () => {
    expect(wrapIndex(-10, 3)).toBe(2)
    expect(wrapIndex(13, 3)).toBe(1)
  })
  it('settles on the same project at 30, 60 and 120 fps without overshooting', () => {
    for (const fps of [30, 60, 120]) {
      let state = { position: 0, velocity: 0 }
      for (let i = 0; i < fps; i++) {
        state = springStep(state.position, state.velocity, 3, 1 / fps)
        expect(state.position).toBeLessThanOrEqual(3)
      }
      expect(state.position).toBeCloseTo(3, 3)
    }
  })
  it('preserves momentum when input reverses and settles on the new target', () => {
    let state = springStep(0, 0, 2, .1)
    expect(state.velocity).toBeGreaterThan(0)
    for (let i = 0; i < 120; i++) state = springStep(state.position, state.velocity, -1, 1 / 60)
    expect(state.position).toBeCloseTo(-1, 4)
    expect(state.velocity).toBeCloseTo(0, 4)
  })
})


describe('project pointer and card gestures', () => {
  const dates = ['2025', '2026 → Now', '2024']
  it('places projects against the dated timeline stops', () => {
    expect(projectDatePosition('2024')).toBe(0)
    expect(projectDatePosition('2025')).toBe(.25)
    expect(projectDatePosition('2026')).toBe(.5)
    expect(projectDatePosition('2026 → Now')).toBe(1)
  })
  it('tracks fractional barrel movement, including reverse and wraparound', () => {
    expect(projectPointerPosition(.5, dates)).toBe(.625)
    expect(projectPointerPosition(1.5, dates)).toBe(.5)
    expect(projectPointerPosition(2.5, dates)).toBe(.125)
    expect(projectPointerPosition(-.5, dates)).toBe(.125)
  })
  it('commits deliberate horizontal pulls and quick flicks in both directions', () => {
    expect(cardSwipeDirection(-100, 8, -.1, 500)).toBe(1)
    expect(cardSwipeDirection(100, 8, .1, 500)).toBe(-1)
    expect(cardSwipeDirection(-30, 4, -.7, 500)).toBe(1)
  })
  it('rejects taps, short pulls and vertical page scrolling', () => {
    expect(cardSwipeDirection(10, 0, 1, 500)).toBeNull()
    expect(cardSwipeDirection(35, 0, .1, 500)).toBeNull()
    expect(cardSwipeDirection(90, 150, 1, 500)).toBeNull()
  })
})
