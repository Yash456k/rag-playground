import { useEffect, useRef, useState } from 'react'

// A torus knot, projected from 3D. Keeping this small avoids a WebGL dependency
// for one decorative object, and works on devices without hardware acceleration.
export function KineticSculpture() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rotation = useRef({ x: .48, y: .3 })
  const [paused, setPaused] = useState(false)
  const [reducedMotion, setReducedMotion] = useState(false)

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReducedMotion(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!canvas || !context) return
    const host = canvas.parentElement!
    let width = 0, height = 0, frame = 0, last = 0
    let visible = true, dragging = false, pointerX = 0, pointerY = 0
    const lines = Array.from({ length: 22 }, (_, strand) =>
      Array.from({ length: 181 }, (_, sample) => {
        const t = sample / 180 * Math.PI * 2
        const v = strand / 22 * Math.PI * 2
        const r = 1.13 + .36 * Math.cos(3 * t)
        const tube = .115
        return [
          (r + tube * Math.cos(v)) * Math.cos(2 * t),
          (r + tube * Math.cos(v)) * Math.sin(2 * t),
          .5 * Math.sin(3 * t) + tube * Math.sin(v),
        ]
      }),
    )
    const draw = (time: number) => {
      frame = 0
      if (!visible || document.hidden) return
      const delta = Math.min(time - last, 50)
      last = time
      if (!paused && !reducedMotion && !dragging) rotation.current.y += delta * .00012
      const { x: rx, y: ry } = rotation.current
      context.clearRect(0, 0, width, height)
      const scale = Math.min(width * .25, height * .25)
      const segments: { x: number; y: number; bx: number; by: number; z: number; accent: boolean }[] = []
      for (let strand = 0; strand < lines.length; strand++) {
        const points = lines[strand].map(([x, y, z]) => {
          const dx = x * Math.cos(ry) + z * Math.sin(ry)
          const dz = -x * Math.sin(ry) + z * Math.cos(ry)
          const dy = y * Math.cos(rx) - dz * Math.sin(rx)
          const depth = y * Math.sin(rx) + dz * Math.cos(rx)
          const perspective = 4.6 / (4.6 - depth)
          return { x: width / 2 + dx * scale * perspective, y: height / 2 + dy * scale * perspective, z: depth }
        })
        for (let i = 1; i < points.length; i++) {
          const a = points[i - 1], b = points[i]
          segments.push({ x: a.x, y: a.y, bx: b.x, by: b.y, z: (a.z + b.z) / 2, accent: strand === 5 })
        }
      }
      segments.sort((a, b) => a.z - b.z)
      for (const s of segments) {
        context.beginPath()
        context.moveTo(s.x, s.y)
        context.lineTo(s.bx, s.by)
        context.strokeStyle = s.accent ? '#c2462f' : `rgba(41,43,40,${.1 + (s.z + 1.7) / 3.4 * .48})`
        context.lineWidth = s.accent ? 1.9 : .65
        context.stroke()
      }
      if (!paused && !reducedMotion || dragging) frame = requestAnimationFrame(draw)
    }
    const requestDraw = () => { if (!frame) frame = requestAnimationFrame(draw) }
    const resize = new ResizeObserver(() => {
      const bounds = canvas.getBoundingClientRect()
      width = bounds.width; height = bounds.height
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(width * pixelRatio)
      canvas.height = Math.round(height * pixelRatio)
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
      requestDraw()
    })
    resize.observe(canvas)
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting
      if (visible) { last = performance.now(); requestDraw() }
    })
    observer.observe(host)
    const onVisibility = () => { if (!document.hidden) { last = performance.now(); requestDraw() } }
    const down = (event: PointerEvent) => {
      dragging = true; pointerX = event.clientX; pointerY = event.clientY
      canvas.setPointerCapture(event.pointerId)
    }
    const move = (event: PointerEvent) => {
      if (!dragging) return
      rotation.current.y += (event.clientX - pointerX) * .008
      rotation.current.x += (event.clientY - pointerY) * .008
      pointerX = event.clientX; pointerY = event.clientY
      requestDraw()
    }
    const up = () => { dragging = false }
    const key = (event: KeyboardEvent) => {
      if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return
      event.preventDefault()
      rotation.current[event.key === 'ArrowLeft' || event.key === 'ArrowRight' ? 'y' : 'x'] += event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -.15 : .15
      requestDraw()
    }
    canvas.addEventListener('pointerdown', down)
    canvas.addEventListener('pointermove', move)
    canvas.addEventListener('pointerup', up)
    canvas.addEventListener('pointercancel', up)
    canvas.addEventListener('lostpointercapture', up)
    canvas.addEventListener('keydown', key)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      cancelAnimationFrame(frame); resize.disconnect(); observer.disconnect()
      canvas.removeEventListener('pointerdown', down); canvas.removeEventListener('pointermove', move)
      canvas.removeEventListener('pointerup', up); canvas.removeEventListener('pointercancel', up)
      canvas.removeEventListener('lostpointercapture', up); canvas.removeEventListener('keydown', key)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [paused, reducedMotion])

  return (
    <figure className="kinetic-object">
      <div className="object-cross cross-one" aria-hidden="true">+</div>
      <div className="object-cross cross-two" aria-hidden="true">+</div>
      <span className="object-coordinate" aria-hidden="true">FIG. 01 / CONTINUOUS CURIOSITY</span>
      <canvas ref={canvasRef} tabIndex={0} role="img" aria-label="Interactive three-dimensional knot. Drag or use arrow keys to rotate." />
      <figcaption><span>A little curiosity, in motion.</span><button type="button" onClick={() => setPaused(!paused)} aria-pressed={paused} disabled={reducedMotion}>{reducedMotion ? 'Motion reduced' : paused ? 'Play motion ↗' : 'Pause motion Ⅱ'}</button></figcaption>
    </figure>
  )
}
