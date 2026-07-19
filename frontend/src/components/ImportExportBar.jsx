import { useRef, useState } from 'react'
import { importItems, exportUrl, importTemplateUrl } from '../api/client'

export default function ImportExportBar({ slug, entity, onImported }) {
  const fileRef = useRef(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const handleFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      await importItems(slug, entity, file)
      onImported?.()
    } catch (err) {
      const detail = err?.response?.data?.detail
      if (detail && typeof detail === 'object') {
        setError(
          `Column mismatch. Missing: [${(detail.missing_columns || []).join(', ')}] Unexpected: [${(detail.unexpected_columns || []).join(', ')}]`,
        )
      } else {
        setError(detail || 'Import failed')
      }
    } finally {
      setBusy(false)
      e.target.value = ''
    }
  }

  return (
    <div className="flex items-center gap-2">
      <a
        href={importTemplateUrl(slug, entity)}
        className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
      >
        Download Template
      </a>
      <a
        href={exportUrl(slug, entity)}
        className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
      >
        Export
      </a>
      <button
        type="button"
        disabled={busy}
        onClick={() => fileRef.current?.click()}
        className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
      >
        {busy ? 'Importing…' : 'Import'}
      </button>
      <input ref={fileRef} type="file" accept=".xlsx" className="hidden" onChange={handleFile} />
      {error && <span className="text-sm text-red-600">{error}</span>}
    </div>
  )
}
