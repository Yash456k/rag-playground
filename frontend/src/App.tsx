import {
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ApiError, getConfig, streamChat } from './api'
import type {
  AssistantMessage,
  ChatMessage,
  EmbeddingConfirmation,
  HistoryItem,
  ModelOption,
  PlaygroundConfig,
  RetrievedChunk,
  StreamEvent,
} from './types'

const QUESTION_LIMIT = 500
const STORAGE_KEYS = {
  embedder: 'rag-playground:embedder',
  model: 'rag-playground:model',
  topK: 'rag-playground:v2:top-k',
  history: 'rag-playground:history-aware',
}

const PREVIEW_CHUNKS: RetrievedChunk[] = [
  {
    id: 'preview-resume',
    title: 'Resume',
    source: 'about-and-experience.md',
    content: 'Full-stack engineering, applied AI, education, and measurable internship experience.',
    score: 0.92,
  },
  {
    id: 'preview-projects',
    title: 'Projects',
    source: 'projects.md',
    content: 'Production projects spanning RAG, concurrent booking systems, and real-time chat.',
    score: 0.89,
  },
  {
    id: 'preview-case-study',
    title: 'RAG Engineering',
    source: 'rag-playground-case-study.md',
    content: 'Retrieval training, pgvector architecture, deployment tradeoffs, and verification.',
    score: 0.86,
  },
]

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
        <span className="brand-mark" aria-hidden="true">YK</span>
        <strong>Yash Khambhatta</strong>
      </a>
      <nav className="site-nav" aria-label="Portfolio navigation">
        <a href="https://www.yashx.me/#work">Work</a>
        <a href="https://www.yashx.me/#about">About</a>
        <a href="https://www.yashx.me/#contact">Contact</a>
        <span
          className={`connection-status ${connected ? 'is-connected' : ''}`}
          role="status"
          aria-label={connected ? 'Pipeline online' : 'Connecting'}
          title={connected ? 'Pipeline online' : 'Connecting'}
        />
      </nav>
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

type ThemeSelectProps = {
  label: string
  options: ModelOption[]
  value: string
  disabled: boolean
  onChange: (id: string) => void
}

function ThemeSelect({ label, options, value, disabled, onChange }: ThemeSelectProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const selected = options.find((option) => option.id === value) ?? options[0]

  useEffect(() => {
    if (!open) return
    const closeOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  return (
    <div className={`theme-select ${open ? 'is-open' : ''}`} ref={rootRef}>
      <span className="control-label">{label}:</span>
      <button
        className="select-trigger"
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{selected?.label}</span>
        <svg viewBox="0 0 12 12" aria-hidden="true"><path d="m2.5 4.5 3.5 3 3.5-3" /></svg>
      </button>
      {open && (
        <div className="select-menu" role="listbox" aria-label={label}>
          {options.map((option) => (
            <button
              type="button"
              role="option"
              aria-selected={option.id === value}
              key={option.id}
              onClick={() => {
                onChange(option.id)
                setOpen(false)
              }}
            >
              <span>{option.label}</span>
              <small>{option.description}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  )
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
      <h2 className="visually-hidden" id="model-panel-title">Choose the route</h2>
      <div className="model-grid">
        <ThemeSelect
          label="Embedding"
          options={config.embedders}
          value={embedderId}
          disabled={disabled}
          onChange={onEmbedderChange}
        />
        <ThemeSelect
          label="LLM"
          options={config.llms}
          value={modelId}
          disabled={disabled}
          onChange={onModelChange}
        />
      </div>
      <details className="route-advanced">
        <summary>Retrieval settings</summary>
        <div className="advanced-content">
          <label>
            Context
            <select
              value={topK}
              onChange={(event) => onTopKChange(Number(event.target.value))}
              disabled={disabled}
            >
              {config.retrieval.selectableTopK.map((value) => (
                <option key={value} value={value}>Top {value}</option>
              ))}
            </select>
          </label>
          <label className="advanced-toggle">
            <input
              type="checkbox"
              checked={historyAware}
              onChange={(event) => onHistoryAwareChange(event.target.checked)}
              disabled={disabled}
            />
            Use recent questions for follow-ups
          </label>
          {embedder && (
            <span className="optimization-readout">
              {embedder.optimization.portfolioTuned ? 'Fine-tuned' : 'Baseline'} ·{' '}
              {embedder.optimization.queryTransform} · threshold{' '}
              {embedder.optimization.minimumScore.toFixed(2)}
            </span>
          )}
        </div>
      </details>
    </section>
  )
}

function SourceCard({ chunk, index }: { chunk: RetrievedChunk; index: number }) {
  return (
    <article className="source-card">
      <div className="source-title">
        <svg className="source-number" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 3.5h7l4 4V20.5H7zM14 3.5v4h4M10 12h5M10 15.5h5" />
        </svg>
        <strong>{chunk.title}</strong>
      </div>
      <span className="source-file">Source: {chunk.source}</span>
      <p>{chunk.content}</p>
      <footer className="source-meta">
        <span>Chunk {index + 1}</span>
        <strong aria-label={`Similarity score ${chunk.score.toFixed(2)}`}>
          Score: {chunk.score.toFixed(2)}
        </strong>
      </footer>
    </article>
  )
}

function RetrievedRail({
  chunks,
  embedding,
  pendingEmbedding,
}: {
  chunks: RetrievedChunk[]
  embedding?: EmbeddingConfirmation
  pendingEmbedding?: string
}) {
  const confirmationLabel = embedding
    ? 'Embedding confirmed'
    : pendingEmbedding
      ? 'Request received'
      : 'Ready for a query'
  const confirmationValue = embedding
    ? `${embedding.label} · ${embedding.vectorDimensions}D`
    : pendingEmbedding
      ? `${pendingEmbedding} · embedding queued`
      : 'Vector receipt appears here'

  return (
    <aside className="source-rail" aria-label="Retrieved chunks">
      <div className={`embedding-confirmation ${embedding ? 'is-confirmed' : ''}`} role="status">
        <span aria-hidden="true" />
        <div>
          <small>{confirmationLabel}</small>
          <strong>{confirmationValue}</strong>
        </div>
      </div>
      <header className="rail-heading">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3.5 5.5c3-.8 5.8-.2 8.5 1.7v12c-2.7-1.9-5.5-2.5-8.5-1.7zM20.5 5.5c-3-.8-5.8-.2-8.5 1.7v12c2.7-1.9 5.5-2.5 8.5-1.7z" />
        </svg>
        <h2>Retrieved chunks</h2>
      </header>
      <div className="source-list">
        {chunks.slice(0, 3).map((chunk, index) => (
          <SourceCard key={`${chunk.id ?? chunk.source}-${index}`} chunk={chunk} index={index} />
        ))}
      </div>
    </aside>
  )
}

function AssistantAnswer({ message }: { message: AssistantMessage }) {
  const isWorking = message.status === 'retrieving' || message.status === 'streaming'
  const servedLabel =
    message.servedModelLabel ??
    (message.status === 'complete' && !message.servedModelId ? 'Local corpus guard' : 'Awaiting provider')

  return (
    <article className={`message assistant-message is-${message.status}`} aria-label="RAG answer">
      <div className="assistant-orb" aria-hidden="true">✧</div>
      <div className="assistant-content">
        <div className="answer-copy" aria-live="polite" aria-busy={isWorking}>
          {message.content ? (
            <>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
              {isWorking && <span className="stream-cursor" aria-hidden="true" />}
            </>
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
        <div className="message-meta">
          <span>{servedLabel}{message.fallbackUsed ? ' · fallback' : ''}</span>
          <span>
            {message.latencies.totalMs === undefined
              ? message.status === 'complete' ? 'Complete' : 'Working…'
              : `${Math.round(message.latencies.totalMs)} ms`}
          </span>
        </div>
      </div>
    </article>
  )
}

function ChatTranscript({ messages }: { messages: ChatMessage[] }) {
  if (messages.length === 0) {
    return (
      <div className="transcript demo-transcript">
        <article className="message user-message" aria-label="Example question">
          <p>What kind of work do you do?</p>
          <time>Ask me anything</time>
        </article>
        <article className="message assistant-message" aria-label="Example answer">
          <div className="assistant-orb" aria-hidden="true">✧</div>
          <div className="assistant-content">
            <div className="answer-copy">
              <p>
                I&apos;m a full-stack developer focused on clean product engineering, real-time systems,
                search, analytics, and applied AI.
              </p>
            </div>
            <div className="message-meta">
              <span>Portfolio corpus</span>
              <span>Ready</span>
            </div>
          </div>
        </article>
      </div>
    )
  }

  return (
    <div className="transcript">
      {messages.map((message) =>
        message.role === 'user' ? (
          <article className="message user-message" key={message.id} aria-label="Your question">
            <p>{message.content}</p>
            <time>Now</time>
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
      <label className="visually-hidden" htmlFor="question-input">Ask about Yash</label>
      <div className="composer-input">
        <textarea
          id="question-input"
          ref={inputRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask me anything about my work…"
          rows={1}
          maxLength={QUESTION_LIMIT}
          disabled={disabled}
          aria-describedby="composer-help composer-count"
        />
        <button type="submit" disabled={!canSubmit} aria-label="Send question">
          <span className="visually-hidden">{disabled ? 'Working' : 'Send'}</span>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M21 3 10.5 13.5M21 3l-6.8 18-3.7-7.5L3 9.8 21 3Z" />
          </svg>
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
  const [topK, setTopK] = useState(3)
  const [historyAware, setHistoryAware] = useState(true)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const chatScrollRef = useRef<HTMLDivElement>(null)
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
    const chatScroll = chatScrollRef.current
    chatScroll?.scrollTo({
      top: chatScroll.scrollHeight,
      behavior: isStreaming ? 'smooth' : 'auto',
    })
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
  const latestAssistant = useMemo(
    () =>
      messages.reduce<AssistantMessage | undefined>(
        (latest, message) => (message.role === 'assistant' ? message : latest),
        undefined,
      ),
    [messages],
  )
  const railChunks =
    latestAssistant && latestAssistant.chunks.length > 0 ? latestAssistant.chunks : PREVIEW_CHUNKS

  const clearChat = useCallback(() => {
    activeRequest.current?.abort()
    activeRequest.current = null
    setMessages([])
    setQuestion('')
    setIsStreaming(false)
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }, [])

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
            case 'embedding':
              return {
                ...answer,
                embedding: {
                  embedder: event.embedder,
                  label: event.label,
                  dimensions: event.dimensions,
                  vectorDimensions: event.vectorDimensions,
                  embeddingMs: event.embeddingMs,
                },
                latencies: { ...answer.latencies, embeddingMs: event.embeddingMs },
              }
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
      <div className="background-art" aria-hidden="true">
        <span className="shape shape-one" />
        <span className="shape shape-two" />
        <span className="shape shape-three" />
      </div>
      <AppHeader connected />
      <main className="portfolio-card">
        <section className="chat-column" aria-labelledby="page-title">
          <button
            className="clear-chat"
            type="button"
            onClick={clearChat}
            disabled={messages.length === 0 && !question}
          >
            Clear chat
          </button>
          <header className="card-intro">
            <span className="sparkle-mark" aria-hidden="true">✦</span>
            <h1 id="page-title">Chat with <em>my portfolio</em></h1>
            <p>I use AI + RAG to answer from my résumé, projects, and experience.</p>
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
          </header>
          <div className="chat-scroll" ref={chatScrollRef}>
            <ChatTranscript messages={messages} />
          </div>
          <Composer
            value={question}
            disabled={isStreaming}
            onChange={setQuestion}
            onSubmit={() => void submitQuestion()}
            inputRef={inputRef}
          />
        </section>
        <RetrievedRail
          chunks={railChunks}
          embedding={latestAssistant?.embedding}
          pendingEmbedding={latestAssistant && !latestAssistant.embedding ? latestAssistant.embedderLabel : undefined}
        />
      </main>
    </div>
  )
}

export default App
