import { ActivityDeck } from './ActivityDeck'



type LandingSectionProps = {
  onNavigate: (path: string) => void
}

export function LandingSection({ onNavigate }: LandingSectionProps) {
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
          <a href="/projects" onClick={(event) => { event.preventDefault(); onNavigate('/projects') }}>Projects</a>
          <a href="/about" onClick={(event) => { event.preventDefault(); onNavigate('/about') }}>About me</a>
          <a className="nav-contact" href="mailto:yash456k@gmail.com">Let&apos;s talk</a>
        </nav>
      </header>

      <div className="landing-hero">
        <div className="landing-copy">
          <p className="hero-overline"><span /> Full-stack engineer <span className="hero-overline-divider">/</span> Applied AI</p>
          <h1 id="landing-title">
            I build stuff
            <em>I find interesting.</em>
          </h1>
          <p className="landing-summary">
            Thoughtful interfaces. Reliable systems. A little applied AI.
            I build across the stack, and care about how it all fits together.
          </p>
          <div className="landing-actions">
            <a className="primary-link" href="#work">Explore selected work <span aria-hidden="true">↘</span></a>
            <a className="text-link" href="#playground">Or ask my portfolio</a>
          </div>
        </div>

        <ActivityDeck />
      </div>

      <div className="landing-footer">
        <p className="landing-signature"><span className="signature-dot" /> Currently building at <strong>AIVID Techvision</strong></p>
        <a className="scroll-cue" href="#work" aria-label="Continue to experience and projects">
          <span>Scroll to explore</span>
          <b aria-hidden="true">↓</b>
        </a>
      </div>
    </section>
  )
}
