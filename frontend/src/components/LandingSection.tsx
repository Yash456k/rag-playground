import { ActivityDeck } from './ActivityDeck'
import { KineticSculpture } from './KineticSculpture'

type LandingSectionProps = { onNavigate: (path: string) => void }

export function LandingSection({ onNavigate }: LandingSectionProps) {
  return (
    <section className="portfolio-section landing-section" id="home" aria-labelledby="landing-title">
      <header className="portfolio-nav">
        <a className="portfolio-wordmark" href="#home" aria-label="Yash Khambhatta, home"><span className="wordmark-symbol" aria-hidden="true">y.</span> Yash Khambhatta</a>
        <span className="nav-discipline">Engineering / Applied AI</span>
        <nav aria-label="Portfolio">
          <a href="/projects" onClick={(event) => { event.preventDefault(); onNavigate('/projects') }}>Work</a>
          <a href="/about" onClick={(event) => { event.preventDefault(); onNavigate('/about') }}>About</a>
          <a className="nav-contact" href="mailto:yash456k@gmail.com">Let’s talk <span aria-hidden="true">↗</span></a>
        </nav>
      </header>
      <div className="landing-hero">
        <div className="landing-copy">
          <p className="hero-overline"><span /> Full-stack engineer. Relentlessly curious.</p>
          <h1 id="landing-title">Ideas into<em>working things.</em></h1>
          <p className="landing-summary">I build the interface, the systems behind it,<br className="desktop-break" /> and the intelligence that connects them.</p>
          <div className="landing-actions">
            <a className="primary-link" href="#work">Explore my work <span aria-hidden="true">↘</span></a>
            <a className="text-link" href="#playground">Ask this portfolio <span aria-hidden="true">↗</span></a>
          </div>
        </div>
        <KineticSculpture />
      </div>
      <div className="activity-instrument"><ActivityDeck /></div>
      <div className="landing-footer">
        <p className="landing-signature"><span className="signature-dot" /> Building at <strong>AIVID Techvision</strong></p>
        <span className="footer-note">Thoughtfully made. Always evolving.</span>
        <a className="scroll-cue" href="#work">The work, below <b aria-hidden="true">↓</b></a>
      </div>
    </section>
  )
}
