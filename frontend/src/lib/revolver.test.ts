import { describe, expect, it } from 'vitest'
import { springStep, wrapIndex } from './revolver'

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
