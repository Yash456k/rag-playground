import { useEffect, useState } from 'react'

const sections = [
  { id: 'home', label: 'Introduction' },
  { id: 'work', label: 'Experience and projects' },
  { id: 'playground', label: 'Ask AI' },
  { id: 'about', label: 'About and contact' },
] as const

export function SectionNavigator() {
  const [activeSection, setActiveSection] = useState('home')

  useEffect(() => {
    const root = document.querySelector<HTMLElement>('.portfolio-site')
    if (!root) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        if (visible?.target.id) setActiveSection(visible.target.id)
      },
      { root, threshold: [0.4, 0.6, 0.8] },
    )

    sections.forEach(({ id }) => {
      const section = document.getElementById(id)
      if (section) observer.observe(section)
    })

    return () => observer.disconnect()
  }, [])

  return (
    <nav className="section-navigator" aria-label="Portfolio sections">
      {sections.map((section, index) => (
        <a
          className={activeSection === section.id ? 'is-active' : ''}
          href={`#${section.id}`}
          key={section.id}
          aria-label={`Go to ${section.label}`}
          aria-current={activeSection === section.id ? 'page' : undefined}
        >
          <span>{String(index + 1).padStart(2, '0')}</span>
          <b>{section.label}</b>
        </a>
      ))}
    </nav>
  )
}
