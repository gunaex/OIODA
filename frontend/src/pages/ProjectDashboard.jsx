import { useOutletContext } from 'react-router-dom'

// Placeholder — the real dashboard (pass rate, evidence completeness,
// defects by severity, go-live readiness) lands in rebuild Phase 6. This
// Phase 1 stub only proves the /:slug route, project-context loading, and
// the Layout shell work end-to-end.
export default function ProjectDashboard() {
  const { project } = useOutletContext()

  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-500">
        Dashboard, test suites, cycles, and reports land in later rebuild phases — see{' '}
        <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">docs/ROADMAP.md</code>.
      </p>
      {project && (
        <div className="bg-white border border-gray-200 rounded-lg p-5 max-w-md">
          <p className="text-sm text-gray-900 font-medium">{project.name}</p>
          <p className="text-xs text-gray-500 mt-1">{project.slug}</p>
          {project.external_project_url && (
            <a
              href={project.external_project_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-emerald-600 hover:underline mt-2 inline-block"
            >
              Back to PM-Again &rarr;
            </a>
          )}
        </div>
      )}
    </div>
  )
}
