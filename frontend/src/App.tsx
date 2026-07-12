import {
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { ApiError, getConfig, streamChat } from './api'
import type {
  AssistantMessage,
  ChatMessage,
  HistoryItem,
  Latencies,
  ModelOption,
  PlaygroundConfig,
  RetrievedChunk,
  StreamEvent,
} from './types'

const QUESTION_LIMIT = 500
const STORAGE_KEYS = {
  embedder: 'rag-playground:embedder',
  model: 'rag-playground:model',
  topK: 'rag-playground:top-k',
  history: 'rag-playground:history-aware',
}

function newId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}

function optionLabel(options: ModelOption[], id: string | null | undefined): string | undefined {
  if (!id) return undefined
  return options.find((option) => option.id === id)?.label
}

function storedChoice(key: string, options: ModelOption[], fallback: string): string {
  const stored = window.localStorage.getItem(key)
  return stored && options.some((option) => option.id === stored) ? stored : fallback
}

function updateAssistant(
  messages: ChatMessage[],
  messageId: string,
  update: (message: AssistantMessage) => AssistantMessage,
): ChatMessage[] {
  return messages.map((message) =>
    message.id === messageId && message.role === 'assistant' ? update(message) : message,
  )
}

function AppHeader({ connected }: { connected: boolean }) {
  return (
    <header className="site-header">
      <a className="brand" href="#top" aria-label="Yash Khambhatta RAG Playground home">
        <span className="brand-mark" aria-hidden="true">
          YK
        </span>
        <span className="brand-copy">
          <strong>RAG Playground</strong>
          <span>Yash Khambhatta</span>
        </span>
      </a>
      <div className={`connection-status ${connected ? 'is-connected' : ''}`} role="status">
        <span className="status-dot" aria-hidden="true" />
        {connected ? 'Pipeline online' : 'Connecting'}
      </div>
    </header>
  )
}

function LoadingScreen({ error, onRetry }: { error?: string; onRetry: () => void }) {
  return (
    <div className="app-shell" id="top">
      <AppHeader connected={false} />
      <main className="load-state">
        <div className="load-orbit" aria-hidden="true">
          <span />
        </div>
        <p className="eyebrow">CONFIGURING RETRIEVAL GRAPH</p>
        <h1>{error ? 'The pipeline did not answer.' : 'Loading the model ladder…'}</h1>
        <p>{error ?? 'Fetching the live embedders and generation models from the API.'}</p>
        {error && (
          <button className="retry-button" type="button" onClick={onRetry}>
            Retry connection
          </button>
        )}
      </main>
    </div>
  )
}

type ModelControlsProps = {
  config: PlaygroundConfig
  embedderId: string
  modelId: string
  topK: number
  historyAware: boolean
  disabled: boolean
  onEmbedderChange: (id: string) => void
  onModelChange: (id: string) => void
  onTopKChange: (value: number) => void
  onHistoryAwareChange: (value: boolean) => void
}

function ModelControls({
  config,
  embedderId,
  modelId,
  topK,
  historyAware,
  disabled,
  onEmbedderChange,
  onModelChange,
  onTopKChange,
  onHistoryAwareChange,
}: ModelControlsProps) {
  const embedder = config.embedders.find((item) => item.id === embedderId)

  return (
    <section className="model-panel" aria-labelledby="model-panel-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">ROUTE</p>
          <h2 id="model-panel-title">Retrieval setup</h2>
        </div>
        {embedder && (
          <div className="optimization-readout" aria-label="Active retrieval optimizations">
            <b>{embedder.optimization.portfolioTuned ? 'Fine-tuned' : 'Baseline'}</b>
            <span>{embedder.optimization.queryTransform}</span>
            <span>threshold {embedder.optimization.minimumScore.toFixed(2)}</span>
          </div>
        )}
      </div>
      <div className="model-grid">
        <label className="model-control">
          <span className="control-label">Embedder</span>
          <span className="select-wrap">
            <select
              value={embedderId}
              onChange={(event) => onEmbedderChange(event.target.value)}
              disabled={disabled}
            >
              {config.embedders.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </span>
        </label>

        <label className="model-control">
          <span className="control-label">Generator</span>
          <span className="select-wrap">
            <select
              value={modelId}
              onChange={(event) => onModelChange(event.target.value)}
              disabled={disabled}
            >
              {config.llms.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </span>
        </label>

        <label className="model-control">
          <span className="control-label">Context</span>
          <span className="select-wrap">
            <select
              value={topK}
              onChange={(event) => onTopKChange(Number(event.target.value))}
              disabled={disabled}
            >
              {config.retrieval.selectableTopK.map((value) => (
                <option key={value} value={value}>
                  Top {value} passages
                </option>
              ))}
            </select>
          </span>
        </label>

        <label className="model-control toggle-control">
          <span className="control-label">Follow-ups</span>
          <span className="toggle-line">
            <input
              type="checkbox"
              checked={historyAware}
              onChange={(event) => onHistoryAwareChange(event.target.checked)}
              disabled={disabled}
            />
            <strong>{historyAware ? 'Use history' : 'Question only'}</strong>
          </span>
        </label>
      </div>
    </section>
  )
}

const latencyStages: Array<{ key: keyof Latencies; label: string }> = [
  { key: 'embeddingMs', label: 'Embed' },
  { key: 'retrievalMs', label: 'Retrieve' },
  { key: 'firstTokenMs', label: 'First token' },
  { key: 'generationMs', label: 'Generate' },
  { key: 'totalMs', label: 'Total' },
]

function LatencyTrace({ latencies }: { latencies: Latencies }) {
  return (
    <div className="latency-trace" aria-label="Pipeline latency">
      {latencyStages.map((stage) => {
        const value = latencies[stage.key]
        return (
          <div className="latency-stage" key={stage.key}>
            <span>{stage.label}</span>
            <strong>{value === undefined ? '—' : `${Math.round(value)} ms`}</strong>
          </div>
        )
      })}
    </div>
  )
}

function SourceCard({ chunk, index }: { chunk: RetrievedChunk; index: number }) {
  const percent = Math.max(0, Math.min(100, chunk.score * 100))

  return (
    <article className="source-card">
      <header className="source-header">
        <span className="source-number">S{index + 1}</span>
        <div className="source-title">
          <strong>{chunk.title}</strong>
          <span>{chunk.source}</span>
        </div>
        <div className="score" aria-label={`Similarity score ${chunk.score.toFixed(3)}`}>
          <strong>{chunk.score.toFixed(3)}</strong>
          <span>score</span>
        </div>
      </header>
      <div className="score-track" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </div>
      <p>{chunk.content}</p>
    </article>
  )
}

function AssistantAnswer({ message }: { message: AssistantMessage }) {
  const isWorking = message.status === 'retrieving' || message.status === 'streaming'
  const servedLabel =
    message.servedModelLabel ??
    (message.status === 'complete' && !message.servedModelId ? 'Local corpus guard' : 'Awaiting provider')

  return (
    <article className={`message assistant-message is-${message.status}`} aria-label="RAG answer">
      <div className="message-rail" aria-hidden="true">
        <span>AI</span>
      </div>
      <div className="answer-body">
        <header className="answer-heading">
          <div>
            <span className="answer-kicker">GROUNDED RESPONSE</span>
            <span className={`answer-state state-${message.status}`}>
              {message.status === 'retrieving' && 'Retrieving'}
              {message.status === 'streaming' && 'Streaming'}
              {message.status === 'complete' && 'Complete'}
              {message.status === 'error' && 'Interrupted'}
            </span>
          </div>
          {message.requestId && <code title="Request ID">{message.requestId.slice(0, 8)}</code>}
        </header>

        <div className="selection-snapshot" aria-label="Models used for this answer">
          <span>
            <small>EMBED</small>
            {message.embedderLabel} · K{message.topK} · {message.historyAware ? 'history' : 'question only'}
          </span>
          <span>
            <small>REQUESTED</small>
            {message.requestedModelLabel}
          </span>
          <span>
            <small>SERVED</small>
            {servedLabel}
          </span>
          {message.fallbackUsed && <b className="fallback-badge">FALLBACK</b>}
        </div>

        <div className="answer-copy" aria-live="polite" aria-busy={isWorking}>
          {message.content ? (
            <p>
              {message.content}
              {isWorking && <span className="stream-cursor" aria-hidden="true" />}
            </p>
          ) : message.status === 'error' ? null : (
            <div className="thinking-line">
              <span />
              <span />
              <span />
              <em>Searching Yash&apos;s corpus</em>
            </div>
          )}
          {message.error && (
            <div className="answer-error" role="alert">
              <strong>Request stopped</strong>
              <span>{message.error}</span>
            </div>
          )}
        </div>

        <section className="trace-block" aria-label="Answer trace">
          <div className="trace-heading">
            <div>
              <span className="trace-icon" aria-hidden="true">
                ↳
              </span>
              <strong>Pipeline trace</strong>
            </div>
            <span>
              {message.chunks.length} chunk{message.chunks.length === 1 ? '' : 's'} retrieved
            </span>
          </div>
          <LatencyTrace latencies={message.latencies} />
        </section>

        {message.chunks.length > 0 ? (
          <section className="sources" aria-label="Retrieved source chunks">
            <div className="sources-heading">
              <strong>Retrieved context</strong>
              <span>ranked by cosine similarity</span>
            </div>
            <div className="source-list">
              {message.chunks.map((chunk, index) => (
                <SourceCard key={`${chunk.id ?? chunk.source}-${index}`} chunk={chunk} index={index} />
              ))}
            </div>
          </section>
        ) : (
          message.status === 'complete' && (
            <p className="empty-sources">No corpus chunks met the retrieval threshold for this question.</p>
          )
        )}
      </div>
    </article>
  )
}

function ChatTranscript({ messages }: { messages: ChatMessage[] }) {
  if (messages.length === 0) {
    return (
      <div className="empty-chat">
        <div className="empty-glyph" aria-hidden="true">
          <span>?</span>
        </div>
        <p className="eyebrow">CORPUS READY</p>
        <h2>Ask what the résumé cannot show at a glance.</h2>
        <p>
          Explore Yash&apos;s experience, technical decisions, projects, skills, and education. Every answer
          arrives with the evidence that shaped it.
        </p>
      </div>
    )
  }

  return (
    <div className="transcript">
      {messages.map((message) =>
        message.role === 'user' ? (
          <article className="message user-message" key={message.id} aria-label="Your question">
            <div className="user-message-label">YOU</div>
            <p>{message.content}</p>
          </article>
        ) : (
          <AssistantAnswer key={message.id} message={message} />
        ),
      )}
    </div>
  )
}

type ComposerProps = {
  value: string
  disabled: boolean
  onChange: (value: string) => void
  onSubmit: () => void
  inputRef: React.RefObject<HTMLTextAreaElement | null>
}

function Composer({ value, disabled, onChange, onSubmit, inputRef }: ComposerProps) {
  const canSubmit = value.trim().length >= 2 && !disabled

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (canSubmit) onSubmit()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      if (canSubmit) onSubmit()
    }
  }

  return (
    <form className="composer" onSubmit={submit} aria-label="Ask Yash's portfolio">
      <label htmlFor="question-input">Ask about Yash</label>
      <div className="composer-input">
        <textarea
          id="question-input"
          ref={inputRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="What did Yash build, and what engineering tradeoffs did he make?"
          rows={1}
          maxLength={QUESTION_LIMIT}
          disabled={disabled}
          aria-describedby="composer-help composer-count"
        />
        <button type="submit" disabled={!canSubmit} aria-label="Send question">
          <span>{disabled ? 'Working' : 'Ask'}</span>
          <span className="send-arrow" aria-hidden="true">
            ↗
          </span>
        </button>
      </div>
      <div className="composer-meta">
        <span id="composer-help">Enter to send · Shift + Enter for a new line</span>
        <span id="composer-count" className={value.length > QUESTION_LIMIT * 0.9 ? 'near-limit' : ''}>
          {value.length}/{QUESTION_LIMIT}
        </span>
      </div>
    </form>
  )
}

function App() {
  const [config, setConfig] = useState<PlaygroundConfig | null>(null)
  const [configError, setConfigError] = useState<string>()
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [embedderId, setEmbedderId] = useState('')
  const [modelId, setModelId] = useState('')
  const [topK, setTopK] = useState(5)
  const [historyAware, setHistoryAware] = useState(true)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const transcriptEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const activeRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    void getConfig(controller.signal)
      .then((nextConfig) => {
        const nextEmbedder = storedChoice(
          STORAGE_KEYS.embedder,
          nextConfig.embedders,
          nextConfig.defaults.embedder,
        )
        const nextModel = storedChoice(STORAGE_KEYS.model, nextConfig.llms, nextConfig.defaults.llm)
        setConfig(nextConfig)
        setEmbedderId(nextEmbedder)
        setModelId(nextModel)
        const savedTopK = Number(window.localStorage.getItem(STORAGE_KEYS.topK))
        setTopK(nextConfig.retrieval.selectableTopK.includes(savedTopK) ? savedTopK : nextConfig.retrieval.topK)
        setHistoryAware(window.localStorage.getItem(STORAGE_KEYS.history) !== 'false')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setConfigError(error instanceof Error ? error.message : 'The model configuration could not be loaded.')
      })

    return () => controller.abort()
  }, [loadAttempt])

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: isStreaming ? 'smooth' : 'auto', block: 'end' })
  }, [messages, isStreaming])

  useEffect(
    () => () => {
      activeRequest.current?.abort()
    },
    [],
  )

  const selectedEmbedder = useMemo(
    () => config?.embedders.find((item) => item.id === embedderId),
    [config, embedderId],
  )
  const selectedModel = useMemo(
    () => config?.llms.find((item) => item.id === modelId),
    [config, modelId],
  )

  const chooseEmbedder = useCallback((id: string) => {
    setEmbedderId(id)
    window.localStorage.setItem(STORAGE_KEYS.embedder, id)
  }, [])

  const chooseModel = useCallback((id: string) => {
    setModelId(id)
    window.localStorage.setItem(STORAGE_KEYS.model, id)
  }, [])

  const chooseTopK = useCallback((value: number) => {
    setTopK(value)
    window.localStorage.setItem(STORAGE_KEYS.topK, String(value))
  }, [])

  const chooseHistoryAware = useCallback((value: boolean) => {
    setHistoryAware(value)
    window.localStorage.setItem(STORAGE_KEYS.history, String(value))
  }, [])

  const submitQuestion = useCallback(async () => {
    const cleanQuestion = question.trim().replace(/\s+/g, ' ')
    if (
      !config ||
      !selectedEmbedder ||
      !selectedModel ||
      cleanQuestion.length < 2 ||
      isStreaming
    ) {
      return
    }

    const history: HistoryItem[] = messages
      .filter((message) => message.content.trim())
      .slice(-6)
      .map((message) => ({ role: message.role, content: message.content.slice(0, 700) }))
    const userMessage: ChatMessage = {
      id: newId('user'),
      role: 'user',
      content: cleanQuestion,
    }
    const answerId = newId('answer')
    const assistantMessage: AssistantMessage = {
      id: answerId,
      role: 'assistant',
      content: '',
      status: 'retrieving',
      embedderId,
      embedderLabel: selectedEmbedder.label,
      topK,
      historyAware,
      requestedModelId: modelId,
      requestedModelLabel: selectedModel.label,
      fallbackUsed: false,
      attempts: [],
      chunks: [],
      latencies: {},
    }
    const controller = new AbortController()
    activeRequest.current = controller
    setQuestion('')
    setIsStreaming(true)
    setMessages((current) => [...current, userMessage, assistantMessage])
    let terminalEventSeen = false

    const handleEvent = (event: StreamEvent) => {
      if (event.type === 'done' || event.type === 'error') terminalEventSeen = true
      setMessages((current) =>
        updateAssistant(current, answerId, (answer) => {
          switch (event.type) {
            case 'meta':
              return { ...answer, requestId: event.requestId }
            case 'sources':
              return { ...answer, chunks: event.chunks, latencies: event.latencies }
            case 'model':
              return {
                ...answer,
                status: 'streaming',
                servedModelId: event.servedModel,
                servedModelLabel: optionLabel(config.llms, event.servedModel) ?? event.servedModel,
                fallbackUsed: event.fallbackUsed,
                attempts: event.attempts,
              }
            case 'token':
              return { ...answer, status: 'streaming', content: answer.content + event.token }
            case 'done':
              return {
                ...answer,
                status: 'complete',
                requestId: event.requestId,
                servedModelId: event.servedModel,
                servedModelLabel: optionLabel(config.llms, event.servedModel),
                fallbackUsed: event.fallbackUsed,
                attempts: event.attempts,
                latencies: event.latencies,
              }
            case 'error':
              return { ...answer, status: 'error', error: event.message }
            case 'usage':
              return answer
          }
        }),
      )
    }

    try {
      await streamChat(
        {
          question: cleanQuestion,
          embedder: embedderId,
          model: modelId,
          history,
          topK,
          useHistory: historyAware,
        },
        handleEvent,
        controller.signal,
      )
      if (!terminalEventSeen) {
        setMessages((current) =>
          updateAssistant(current, answerId, (answer) => ({
            ...answer,
            status: 'error',
            error: 'The answer stream ended before the pipeline sent its completion signal.',
          })),
        )
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      const message =
        error instanceof ApiError || error instanceof Error
          ? error.message
          : 'The request could not be completed.'
      setMessages((current) =>
        updateAssistant(current, answerId, (answer) => ({ ...answer, status: 'error', error: message })),
      )
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null
      setIsStreaming(false)
      window.setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [
    config,
    embedderId,
    historyAware,
    isStreaming,
    messages,
    modelId,
    question,
    selectedEmbedder,
    selectedModel,
    topK,
  ])

  if (!config) {
    return (
      <LoadingScreen
        error={configError}
        onRetry={() => {
          setConfigError(undefined)
          setLoadAttempt((attempt) => attempt + 1)
        }}
      />
    )
  }

  return (
    <div className="app-shell" id="top">
      <div className="ambient-grid" aria-hidden="true" />
      <AppHeader connected />
      <main>
        <section className="hero" aria-labelledby="page-title">
          <div className="hero-copy">
            <p className="eyebrow">PORTFOLIO / RETRIEVAL-AUGMENTED GENERATION</p>
            <h1 id="page-title">
              Ask Yash.
              <br />
              <span>Inspect the answer.</span>
            </h1>
            <p className="hero-lede">
              A transparent chat over my résumé and project writeups. Pick the retrieval and generation
              models, then see exactly what they found and how long each stage took.
            </p>
          </div>
          <aside className="hero-stats" aria-label="Playground features">
            <div>
              <strong>{config.embedders.length.toString().padStart(2, '0')}</strong>
              <span>resident embedding models</span>
            </div>
            <div>
              <strong>{config.llms.length.toString().padStart(2, '0')}</strong>
              <span>generation routes</span>
            </div>
            <div>
              <strong>{config.retrieval.topK.toString().padStart(2, '0')}</strong>
              <span>chunks per retrieval</span>
            </div>
          </aside>
        </section>

        <ModelControls
          config={config}
          embedderId={embedderId}
          modelId={modelId}
          topK={topK}
          historyAware={historyAware}
          disabled={isStreaming}
          onEmbedderChange={chooseEmbedder}
          onModelChange={chooseModel}
          onTopKChange={chooseTopK}
          onHistoryAwareChange={chooseHistoryAware}
        />

        <section className="chat-panel" aria-label="Conversation">
          <div className="chat-topbar">
            <div>
              <span className="terminal-dot" aria-hidden="true" />
              <strong>portfolio_rag.session</strong>
            </div>
            <span>answers constrained to Yash&apos;s corpus</span>
          </div>
          <div className="chat-scroll">
            <ChatTranscript messages={messages} />
            <div ref={transcriptEndRef} />
          </div>
          <Composer
            value={question}
            disabled={isStreaming}
            onChange={setQuestion}
            onSubmit={() => void submitQuestion()}
            inputRef={inputRef}
          />
        </section>
      </main>

      <footer>
        <span>Built as a transparent RAG experiment by Yash Khambhatta.</span>
        <span>Grounded answers · Visible evidence · No general-purpose prompts</span>
      </footer>
    </div>
  )
}

export default App
