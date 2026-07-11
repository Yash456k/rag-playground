import { describe, expect, it } from 'vitest'
import { parseSSEFrame, readSSEStream } from './sse'
import type { StreamEvent } from '../types'

describe('parseSSEFrame', () => {
  it('ignores comments and joins multiple data lines', () => {
    expect(parseSSEFrame(': ping\nevent: update\ndata: {"type":"token",\ndata: "token":"hi"}')).toEqual({
      event: 'update',
      data: '{"type":"token",\n"token":"hi"}',
    })
  })
})

describe('readSSEStream', () => {
  it('parses fragmented CRLF and LF events', async () => {
    const encoder = new TextEncoder()
    const pieces = [
      'data: {"type":"meta","requestId":"abc","embedder":"bge-small",',
      '"requestedModel":"model-a"}\r\n\r\ndata: {"type":"token","token":"Hel',
      'lo"}\n\ndata: {"type":"done","requestId":"abc","requestedModel":"model-a",',
      '"servedModel":"model-a","fallbackUsed":false,"attempts":[],"latencies":{"totalMs":10}}\n\n',
    ]
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        pieces.forEach((piece) => controller.enqueue(encoder.encode(piece)))
        controller.close()
      },
    })
    const events: StreamEvent[] = []

    await readSSEStream(stream, (event) => events.push(event))

    expect(events).toHaveLength(3)
    expect(events[1]).toEqual({ type: 'token', token: 'Hello' })
    expect(events[2]?.type).toBe('done')
  })
})
