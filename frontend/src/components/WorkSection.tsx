const projects = [
  {
    number: '01',
    title: 'RAG Playground',
    summary: 'An inspectable portfolio assistant with six embedding routes, streamed answers, source receipts, and provider fallback.',
    tags: ['React', 'FastAPI', 'pgvector', 'LLM systems'],
    metric: '6 retrieval routes',
    href: 'https://github.com/Yash456k/rag-playground',
    linkLabel: 'View repository',
  },
  {
    number: '02',
    title: 'Nashik Sports Klub',
    summary: 'A production booking platform with race-safe transactions, role-specific workflows, real-time inventory, and automated delivery.',
    tags: ['MERN', 'Transactions', 'AWS', 'Socket.IO'],
    metric: '500-user race test',
    href: 'https://www.nashiksportsklub.com',
    linkLabel: 'Visit live product',
  },
  {
    number: '03',
    title: 'Real-time Chat',
    summary: 'An event-driven messaging product with live conversations, federated authentication, secure sessions, and a Gemini assistant.',
    tags: ['React', 'Node.js', 'MongoDB', 'Firebase'],
    metric: '500+ messages',
    href: 'https://yashchatapp.vercel.app',
    linkLabel: 'Open live demo',
  },
] as const

export function WorkSection() {
  return (
    <section className="portfolio-section work-section" id="work" aria-labelledby="work-title">
      <header className="section-header">
        <a className="portfolio-wordmark" href="#home">Yash Khambhatta</a>
        <p><span>03</span> Selected work</p>
        <a href="#about">About & contact <span aria-hidden="true">↘</span></a>
      </header>

      <div className="work-layout">
        <div className="work-intro">
          <p className="section-kicker"><span /> Built beyond the mockup</p>
          <h2 id="work-title">Selected systems,<br /><em>shipped for real.</em></h2>
          <p>Three projects that show how I approach product thinking, backend correctness, and calm interfaces.</p>
        </div>

        <div className="project-list">
          {projects.map((project) => (
            <article className="project-row" key={project.title}>
              <span className="project-number">{project.number}</span>
              <div className="project-main">
                <div className="project-heading">
                  <h3>{project.title}</h3>
                  <span>{project.metric}</span>
                </div>
                <p>{project.summary}</p>
                <ul aria-label={`${project.title} technologies`}>
                  {project.tags.map((tag) => <li key={tag}>{tag}</li>)}
                </ul>
              </div>
              <a href={project.href} target="_blank" rel="noreferrer" aria-label={`${project.linkLabel}: ${project.title}`}>
                <span>{project.linkLabel}</span>
                <b aria-hidden="true">↗</b>
              </a>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
