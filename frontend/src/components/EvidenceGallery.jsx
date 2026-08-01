import { useEffect, useRef, useState } from 'react'
import { listEvidence, uploadEvidence, evidenceOriginalUrl, archiveEvidence } from '../api/client'
import AnnotationEditor from './AnnotationEditor.jsx'

/** Evidence-first execution requirement (rebuild prompt §13): three
 * capture paths — screen capture, clipboard paste, file upload — all
 * funnel into the same authenticated upload endpoint. */
export default function EvidenceGallery({ slug, cycleId, resultId, canEdit, isAdmin, isLocked }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [openEvidence, setOpenEvidence] = useState(null)
  const fileInputRef = useRef(null)
  const pasteZoneRef = useRef(null)

  const load = () => {
    setLoading(true)
    listEvidence(slug, cycleId, resultId)
      .then(setItems)
      .catch(() => setError('Could not load evidence'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug, cycleId, resultId])

  const doUpload = async (blob, evidenceType, filename) => {
    setUploading(true)
    setError(null)
    try {
      await uploadEvidence(slug, cycleId, resultId, blob, { evidenceType, filename })
      load()
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) doUpload(file, 'UPLOADED_IMAGE', file.name)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handlePaste = (e) => {
    const item = Array.from(e.clipboardData?.items || []).find((i) => i.type.startsWith('image/'))
    if (!item) return
    const blob = item.getAsFile()
    if (blob) doUpload(blob, 'PASTED_IMAGE', 'pasted-image.png')
  }

  const handleScreenCapture = async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true })
      const video = document.createElement('video')
      video.srcObject = stream
      await video.play()
      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      canvas.getContext('2d').drawImage(video, 0, 0)
      stream.getTracks().forEach((t) => t.stop())
      canvas.toBlob((blob) => {
        if (blob) doUpload(blob, 'SCREENSHOT', 'screen-capture.png')
      }, 'image/png')
    } catch {
      setError('Screen capture was cancelled or is not available in this browser context')
    }
  }

  const handleArchive = async (evidenceId) => {
    if (!window.confirm('Archive this evidence? The original file is kept, just hidden from the default view.')) return
    await archiveEvidence(slug, cycleId, resultId, evidenceId)
    load()
  }

  return (
    <div>
      <p className="text-xs font-medium text-gray-500 uppercase mb-2">Evidence ({items.length})</p>

      {canEdit && !isLocked && (
        <div
          ref={pasteZoneRef}
          onPaste={handlePaste}
          tabIndex={0}
          className="flex items-center gap-2 flex-wrap mb-3 p-2 border border-dashed border-gray-300 rounded-md text-xs text-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        >
          <span>Click here then Ctrl+V to paste a screenshot, or:</span>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="px-2 py-1 border border-gray-300 rounded hover:bg-gray-50"
          >
            Upload file
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
          <button
            type="button"
            onClick={handleScreenCapture}
            className="px-2 py-1 border border-gray-300 rounded hover:bg-gray-50"
          >
            Capture screen
          </button>
          {uploading && <span className="text-emerald-600">Uploading…</span>}
        </div>
      )}
      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}

      {loading ? (
        <p className="text-xs text-gray-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-xs text-gray-400">No evidence captured yet.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <div key={item.id} className="relative group">
              <button
                onClick={() => setOpenEvidence(item)}
                className="block w-24 h-24 border border-gray-200 rounded-md overflow-hidden hover:border-emerald-400"
              >
                <img
                  src={evidenceOriginalUrl(slug, cycleId, resultId, item.id)}
                  alt={item.caption || item.original_filename}
                  className="w-full h-full object-cover"
                />
              </button>
              {item.current_revision_no > 0 && (
                <span className="absolute top-1 right-1 bg-emerald-600 text-white text-[9px] px-1 rounded">
                  rev {item.current_revision_no}
                </span>
              )}
              {isAdmin && !isLocked && (
                <button
                  onClick={() => handleArchive(item.id)}
                  className="absolute bottom-1 right-1 bg-white/90 text-red-600 text-[9px] px-1 rounded opacity-0 group-hover:opacity-100"
                >
                  Archive
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {openEvidence && (
        <AnnotationEditor
          slug={slug}
          cycleId={cycleId}
          resultId={resultId}
          evidence={openEvidence}
          canEdit={canEdit && !isLocked}
          onClose={() => setOpenEvidence(null)}
          onSaved={() => {
            load()
          }}
        />
      )}
    </div>
  )
}
