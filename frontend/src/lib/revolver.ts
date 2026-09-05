export function wrapIndex(index: number, length: number) {
  return ((index % length) + length) % length
}

// Critically damped spring, solved analytically so motion is stable at any frame rate.
export function springStep(position: number, velocity: number, target: number, seconds: number) {
  const frequency = 13
  const displacement = position - target
  const impulse = velocity + frequency * displacement
  const decay = Math.exp(-frequency * seconds)
  return {
    position: target + (displacement + impulse * seconds) * decay,
    velocity: (velocity - frequency * impulse * seconds) * decay,
  }
}

// The dated stops are 2024, 2026 and Now; project dates stay in the JSON corpus.
export function projectDatePosition(date: string) {
  if (/now|present/i.test(date)) return 1
  const year = Number(date.match(/20\d{2}/)?.[0] ?? 2024)
  return Math.max(0, Math.min(.5, (year - 2024) / 4))
}

export function projectPointerPosition(position: number, dates: readonly string[]) {
  const lower = Math.floor(position)
  const fraction = position - lower
  const from = projectDatePosition(dates[wrapIndex(lower, dates.length)])
  const to = projectDatePosition(dates[wrapIndex(lower + 1, dates.length)])
  return from + (to - from) * fraction
}

export function cardSwipeDirection(x: number, y: number, velocity: number, width: number): -1 | 1 | null {
  if (Math.abs(x) < 24 || Math.abs(x) < Math.abs(y) * 1.2) return null
  if (Math.abs(x) < Math.min(width * .22, 90) && Math.abs(velocity) < .5) return null
  return x < 0 ? 1 : -1
}
