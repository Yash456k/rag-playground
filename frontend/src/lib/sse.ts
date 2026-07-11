import type { StreamEvent } from '../types'

export type SSEMessage = {
  event?: string
  data: string
}

export function parseSSEFrame(frame: string): SSEMessage | null {
  const data: string[] = []
  let event: string | undefined

  for (const rawLine of frame.split(/\r?\n/)) {
    if (!rawLine || rawLine.startsWith(':')) continue

    const separator = rawLine.indexOf(':')
    const field = separator === -1 ? rawLine : rawLine.slice(0, separator)
    let value = separator === -1 ? '' : rawLine.slice(separator + 1)
    if (value.startsWith(' ')) value = value.slice(1)

    if (field === 'data') data.push(value)
    if (field === 'event') event = value
  }

  if (data.length === 0) return null
  return { event, data: data.join('\n') }
}

function takeFrame(buffer: string): { frame: string; rest: string } | null {
  const boundary = /\r?\n\r?\n/.exec(buffer)
  if (!boundary || boundary.index === undefined) return null

  return {
    frame: buffer.slice(0, boundary.index),
    rest: buffer.slice(boundary.index + boundary[0].length),
  }
}

export async function readSSEStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })

      let next = takeFrame(buffer)
      while (next) {
        buffer = next.rest
        const message = parseSSEFrame(next.frame)
        if (message) onEvent(JSON.parse(message.data) as StreamEvent)
        next = takeFrame(buffer)
      }

      if (done) break
    }

    const finalMessage = parseSSEFrame(buffer.trim())
    if (finalMessage) onEvent(JSON.parse(finalMessage.data) as StreamEvent)
  } finally {
    reader.releaseLock()
  }
}
