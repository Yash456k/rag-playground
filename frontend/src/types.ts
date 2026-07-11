export type ModelOption = {
  id: string
  label: string
  description: string
}

export type EmbedderOption = ModelOption & {
  dimensions: number
}

export type PlaygroundConfig = {
  version: number
  defaults: {
    embedder: string
    llm: string
  }
  embedders: EmbedderOption[]
  llms: ModelOption[]
  retrieval: {
    topK: number
  }
}

export type HistoryItem = {
  role: 'user' | 'assistant'
  content: string
}

export type RetrievedChunk = {
  id?: string | number
  title: string
  source: string
  content: string
  score: number
}

export type Latencies = {
  embeddingMs?: number
  retrievalMs?: number
  firstTokenMs?: number
  generationMs?: number
  totalMs?: number
}

export type FallbackAttempt = {
  model?: string
  reason?: string
  status?: number
  [key: string]: unknown
}

export type StreamEvent =
  | {
      type: 'meta'
      requestId: string
      embedder: string
      requestedModel: string
    }
  | {
      type: 'sources'
      chunks: RetrievedChunk[]
      latencies: Latencies
    }
  | {
      type: 'model'
      servedModel: string
      fallbackUsed: boolean
      attempts: FallbackAttempt[]
    }
  | { type: 'token'; token: string }
  | { type: 'usage'; usage: unknown }
  | {
      type: 'done'
      requestId: string
      requestedModel: string
      servedModel: string | null
      fallbackUsed: boolean
      attempts: FallbackAttempt[]
      latencies: Latencies
    }
  | { type: 'error'; code: string; message: string }

export type UserMessage = {
  id: string
  role: 'user'
  content: string
}

export type AssistantMessage = {
  id: string
  role: 'assistant'
  content: string
  status: 'retrieving' | 'streaming' | 'complete' | 'error'
  embedderId: string
  embedderLabel: string
  requestedModelId: string
  requestedModelLabel: string
  servedModelId?: string | null
  servedModelLabel?: string
  fallbackUsed: boolean
  attempts: FallbackAttempt[]
  chunks: RetrievedChunk[]
  latencies: Latencies
  requestId?: string
  error?: string
}

export type ChatMessage = UserMessage | AssistantMessage
