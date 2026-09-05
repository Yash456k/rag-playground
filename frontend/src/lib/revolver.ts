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
