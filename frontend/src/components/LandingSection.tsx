const highlights = [
  { value: '9.66', label: 'CGPA / 10' },
  { value: '100K+', label: 'records handled daily' },
  { value: '20+', label: 'production features shipped' },
  { value: '150+', label: 'problems solved' },
] as const

export function LandingSection() {
  return (
    <section className="portfolio-section landing-section" id="home" aria-labelledby="landing-title">
      <div className="landing-orbit" aria-hidden="true">
        <span />
      </div>

      <header className="portfolio-nav">
        <a className="portfolio-wordmark" href="#home" aria-label="Yash Khambhatta, home">
          Yash Khambhatta
        </a>
        <nav aria-label="Portfolio">
          <a href="#playground">Ask AI</a>
          <a href="#work">Work</a>
          <a href="#about">About</a>
          <a className="nav-contact" href="mailto:yash456k@gmail.com">Let&apos;s talk</a>
        </nav>
      </header>

      <div className="landing-hero">
        <div className="landing-copy">
          <p className="section-kicker"><span /> Full-stack engineer · Applied AI</p>
          <h1 id="landing-title">
            I build the useful,
            <em>difficult <br className="mobile-title-break" />things.</em>
          </h1>
          <p className="landing-summary">
            Production-minded software across real-time products, search systems,
            data-heavy backends, and grounded AI experiences.
          </p>
          <div className="landing-actions">
            <a className="primary-link" href="#work">Explore selected work <span aria-hidden="true">↘</span></a>
            <a className="text-link" href="#playground">Or ask my portfolio</a>
          </div>
        </div>

        <aside className="landing-note" aria-label="Current focus">
          <span className="note-index">01 — 04</span>
          <div>
            <span className="note-spark" aria-hidden="true">✦</span>
            <p>Currently exploring</p>
            <strong>Retrieval systems that explain themselves.</strong>
          </div>
          <a href="#playground">Open the live RAG lab <span aria-hidden="true">→</span></a>
        </aside>
      </div>

      <div className="landing-footer">
        <p>Ahmedabad, India <span>·</span> Available for ambitious product teams</p>
        <dl className="highlight-strip">
          {highlights.map((highlight) => (
            <div key={highlight.label}>
              <dt>{highlight.value}</dt>
              <dd>{highlight.label}</dd>
            </div>
          ))}
        </dl>
        <a className="scroll-cue" href="#playground" aria-label="Continue to the RAG playground">
          <span>Scroll to explore</span>
          <b aria-hidden="true">↓</b>
        </a>
      </div>
    </section>
  )
}
