import type { ProjectItem } from './projectTypes'

type ProjectDetailProps = {
  project: ProjectItem
  onBack: () => void
}

export function ProjectDetail({ project, onBack }: ProjectDetailProps) {
  return (
    <article className="project-focus-view" aria-labelledby="project-focus-title">
      <header className="project-focus-header">
        <div>
          <span>{project.number}</span>
          <time>{project.date}</time>
        </div>
        <button type="button" onClick={onBack}>Back to revolver <span aria-hidden="true">↙</span></button>
      </header>

      <div className="project-focus-copy">
        <p>{project.eyebrow} · {project.role}</p>
        <h2 id="project-focus-title">{project.title}</h2>
        <strong>{project.summary}</strong>
        <p>{project.detail}</p>
      </div>

      <ul className="project-focus-metrics" aria-label={`${project.title} results`}>
        {project.metrics.map((metric) => <li key={metric}>{metric}</li>)}
      </ul>

      <ul className="project-focus-highlights" aria-label={`${project.title} highlights`}>
        {project.highlights.map((highlight) => <li key={highlight}>{highlight}</li>)}
      </ul>

      <footer className="project-focus-footer">
        <ul aria-label={`${project.title} technologies`}>
          {project.tags.map((tag) => <li key={tag}>{tag}</li>)}
        </ul>
        <nav aria-label={`${project.title} links`}>
          <a href={project.href} target={project.external ? '_blank' : undefined} rel={project.external ? 'noreferrer' : undefined}>
            {project.linkLabel} <span aria-hidden="true">↗</span>
          </a>
          <a href={project.repository} target="_blank" rel="noreferrer">Source <span aria-hidden="true">↗</span></a>
        </nav>
      </footer>
    </article>
  )
}
