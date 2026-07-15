import { ActivityDeck } from './ActivityDeck'

/*
const highlights = [
  { value: '9.66', label: 'CGPA / 10' },
  { value: '100K+', label: 'records handled daily' },
  { value: '20+', label: 'production features shipped' },
  { value: '150+', label: 'problems solved' },
] as const
*/

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
          <a href="#work">Work</a>
          <a href="#projects">Projects</a>
          <a href="#playground">Ask AI</a>
          <a href="#about">About</a>
          <a className="nav-contact" href="mailto:yash456k@gmail.com">Let&apos;s talk</a>
        </nav>
      </header>

      <div className="landing-hero">
        <div className="landing-copy">
          <h1 id="landing-title">
            I build stuff
            <em>I find <br className="mobile-title-break" />interesting.</em>
          </h1>
          <p className="landing-summary">
            Yes, I use AI to build. I can also explain how everything works, ask me anything.
          </p>
          <div className="landing-actions">
            <a className="primary-link" href="#work">Explore selected work <span aria-hidden="true">↘</span></a>
            <a className="text-link" href="#playground">Or ask my portfolio</a>
          </div>
        </div>

        <ActivityDeck />
      </div>

      <div className="landing-footer">
        {/* <dl className="highlight-strip">
          {highlights.map((highlight) => (
            <div key={highlight.label}>
              <dt>{highlight.value}</dt>
              <dd>{highlight.label}</dd>
            </div>
          ))}
        </dl> */}
        <a className="scroll-cue" href="#work" aria-label="Continue to experience and projects">
          <span>Scroll to explore</span>
          <b aria-hidden="true">↓</b>
        </a>
      </div>
    </section>
  )
}
