const experience = [
  {
    period: '2024 — 2025',
    role: 'Full Stack Developer Intern',
    company: 'AIVID Techvision',
    detail: 'Built multi-tenant notification, Microsoft Graph, analytics, and reusable frontend systems.',
  },
  {
    period: '2024',
    role: 'React Web Development Intern',
    company: 'Future AI Power',
    detail: 'Led a four-person frontend team and shipped an AI product-discovery interface.',
  },
  {
    period: '2022 — 2026',
    role: 'B.Tech, Computer Engineering',
    company: 'Indus University',
    detail: 'Maintaining a 9.66/10 CGPA while building production software beyond the classroom.',
  },
] as const

export function AboutSection() {
  return (
    <section className="portfolio-section about-section" id="about" aria-labelledby="about-title">
      <header className="section-header about-header">
        <p><span>04</span> About</p>
      </header>

      <div className="about-layout">
        <div className="about-statement">
          <p className="section-kicker"><span /> The person behind the systems</p>
          <h2 id="about-title">Engineering should feel<br /><em>clear on both sides.</em></h2>
          <p>
            I care about the hard parts beneath a product—data integrity, performance,
            reliability—and the quiet details that make it intuitive above the surface.
          </p>
          <div className="availability-note">
            <span aria-hidden="true" />
            Open to full-time software engineering opportunities
          </div>
        </div>

        <div className="experience-list" aria-label="Experience and education">
          {experience.map((item) => (
            <article key={`${item.company}-${item.period}`}>
              <time>{item.period}</time>
              <div>
                <h3>{item.role}</h3>
                <strong>{item.company}</strong>
                <p>{item.detail}</p>
              </div>
            </article>
          ))}
        </div>
      </div>

      <footer className="contact-footer" id="contact">
        <div>
          <p>Have a difficult, useful thing to build?</p>
          <a href="mailto:yash456k@gmail.com">yash456k@gmail.com <span aria-hidden="true">↗</span></a>
        </div>
        <nav aria-label="Social links">
          <a href="https://github.com/Yash456k" target="_blank" rel="noreferrer">GitHub</a>
          <a href="https://linkedin.com/in/yash-khambhatta/" target="_blank" rel="noreferrer">LinkedIn</a>
          <a href="#playground">RAG Playground</a>
        </nav>
        <p>Designed and engineered by Yash Khambhatta · 2026</p>
      </footer>
    </section>
  )
}
