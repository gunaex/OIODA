import { useEffect, useRef, useState } from 'react'
import { listAnnotations, createAnnotation, evidenceOriginalUrl } from '../api/client'

// Rebuild prompt §14 required tools. Custom vanilla-canvas implementation
// instead of react-konva/Filerobot — see docs/ROADMAP.md Phase 5 for why
// (avoids a new dependency of unproven React 19 compatibility; documented
// decision, not a silent skip of the doc's compatibility-spike request).
const TOOLS = ['select', 'arrow', 'rectangle', 'highlight', 'freehand', 'text', 'callout', 'blur']
const DEFAULT_COLOR = '#f97316' // orange — required default (rebuild prompt §14)

export default function AnnotationEditor({ slug, cycleId, resultId, evidence, canEdit, onClose, onSaved }) {
  const canvasRef = useRef(null)
  const imgRef = useRef(null)
  const [tool, setTool] = useState('arrow')
  const [color, setColor] = useState(DEFAULT_COLOR)
  const [shapes, setShapes] = useState([])
  const [redoStack, setRedoStack] = useState([])
  const [drawing, setDrawing] = useState(null) // in-progress shape
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [imageLoaded, setImageLoaded] = useState(false)

  useEffect(() => {
    const img = new Image()
    img.crossOrigin = 'use-credentials'
    img.onload = () => {
      imgRef.current = img
      setImageLoaded(true)
    }
    img.src = evidenceOriginalUrl(slug, cycleId, resultId, evidence.id)
  }, [slug, cycleId, resultId, evidence.id])

  useEffect(() => {
    if (evidence.current_revision_no === 0) return
    listAnnotations(slug, cycleId, resultId, evidence.id).then((revisions) => {
      const latest = revisions[revisions.length - 1]
      if (latest) {
        try {
          setShapes(JSON.parse(latest.annotation_json))
        } catch {
          // corrupt/unparseable JSON — start fresh rather than crash the editor
        }
      }
    })
  }, [slug, cycleId, resultId, evidence.id, evidence.current_revision_no])

  const redraw = () => {
    const canvas = canvasRef.current
    const img = imgRef.current
    if (!canvas || !img) return
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0)

    const allShapes = drawing ? [...shapes, drawing] : shapes
    let calloutNo = 0
    for (const s of allShapes) {
      ctx.strokeStyle = s.color || DEFAULT_COLOR
      ctx.fillStyle = s.color || DEFAULT_COLOR
      ctx.lineWidth = 3
      if (s.type === 'arrow') {
        drawArrow(ctx, s.x1, s.y1, s.x2, s.y2)
      } else if (s.type === 'rectangle') {
        ctx.strokeRect(s.x, s.y, s.w, s.h)
      } else if (s.type === 'highlight') {
        ctx.globalAlpha = 0.35
        ctx.fillRect(s.x, s.y, s.w, s.h)
        ctx.globalAlpha = 1
      } else if (s.type === 'freehand') {
        ctx.beginPath()
        s.points.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)))
        ctx.stroke()
      } else if (s.type === 'text') {
        ctx.font = 'bold 18px sans-serif'
        ctx.fillText(s.text, s.x, s.y)
      } else if (s.type === 'callout') {
        calloutNo += 1
        ctx.beginPath()
        ctx.arc(s.x, s.y, 14, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = '#fff'
        ctx.font = 'bold 14px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(String(calloutNo), s.x, s.y)
        ctx.textAlign = 'start'
        ctx.textBaseline = 'alphabetic'
      } else if (s.type === 'blur') {
        ctx.save()
        ctx.filter = 'blur(8px)'
        ctx.drawImage(img, s.x, s.y, s.w, s.h, s.x, s.y, s.w, s.h)
        ctx.restore()
      }
    }
  }

  useEffect(redraw, [shapes, drawing, imageLoaded])

  const drawArrow = (ctx, x1, y1, x2, y2) => {
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.stroke()
    const angle = Math.atan2(y2 - y1, x2 - x1)
    const headLen = 12
    ctx.beginPath()
    ctx.moveTo(x2, y2)
    ctx.lineTo(x2 - headLen * Math.cos(angle - Math.PI / 6), y2 - headLen * Math.sin(angle - Math.PI / 6))
    ctx.moveTo(x2, y2)
    ctx.lineTo(x2 - headLen * Math.cos(angle + Math.PI / 6), y2 - headLen * Math.sin(angle + Math.PI / 6))
    ctx.stroke()
  }

  const commitShape = (shape) => {
    setShapes((prev) => [...prev, shape])
    setRedoStack([])
  }

  const pointerPos = (e) => {
    const rect = canvasRef.current.getBoundingClientRect()
    const scaleX = canvasRef.current.width / rect.width
    const scaleY = canvasRef.current.height / rect.height
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY }
  }

  const handleMouseDown = (e) => {
    if (!canEdit || tool === 'select') return
    const { x, y } = pointerPos(e)
    if (tool === 'text') {
      const text = window.prompt('Callout text:')
      if (text) commitShape({ type: 'text', x, y, text, color })
      return
    }
    if (tool === 'callout') {
      commitShape({ type: 'callout', x, y, color })
      return
    }
    if (tool === 'freehand') {
      setDrawing({ type: 'freehand', points: [[x, y]], color })
      return
    }
    setDrawing({ type: tool, x1: x, y1: y, x2: x, y2: y, x, y, w: 0, h: 0, color })
  }

  const handleMouseMove = (e) => {
    if (!drawing) return
    const { x, y } = pointerPos(e)
    if (drawing.type === 'freehand') {
      setDrawing({ ...drawing, points: [...drawing.points, [x, y]] })
    } else if (drawing.type === 'arrow') {
      setDrawing({ ...drawing, x2: x, y2: y })
    } else {
      setDrawing({ ...drawing, x: Math.min(drawing.x1, x), y: Math.min(drawing.y1, y), w: Math.abs(x - drawing.x1), h: Math.abs(y - drawing.y1) })
    }
  }

  const handleMouseUp = () => {
    if (!drawing) return
    commitShape(drawing)
    setDrawing(null)
  }

  const undo = () => {
    if (shapes.length === 0) return
    setRedoStack((prev) => [shapes[shapes.length - 1], ...prev])
    setShapes((prev) => prev.slice(0, -1))
  }
  const redo = () => {
    if (redoStack.length === 0) return
    setShapes((prev) => [...prev, redoStack[0]])
    setRedoStack((prev) => prev.slice(1))
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await createAnnotation(slug, cycleId, resultId, evidence.id, {
        annotation_json: JSON.stringify(shapes),
        change_summary: `${shapes.length} annotation(s)`,
      })
      onSaved?.()
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save annotation')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-lg shadow-2xl p-4 max-w-4xl w-full max-h-[90vh] overflow-auto"
      >
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-gray-900">{evidence.caption || evidence.original_filename}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            ✕
          </button>
        </div>

        {canEdit && (
          <div className="flex items-center gap-2 flex-wrap mb-3">
            {TOOLS.map((t) => (
              <button
                key={t}
                onClick={() => setTool(t)}
                className={`px-2 py-1 text-xs rounded border ${tool === t ? 'bg-emerald-600 text-white border-emerald-600' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}
              >
                {t}
              </button>
            ))}
            <input type="color" value={color} onChange={(e) => setColor(e.target.value)} className="w-7 h-7 border border-gray-300 rounded" />
            <button onClick={undo} disabled={shapes.length === 0} className="px-2 py-1 text-xs border border-gray-300 rounded disabled:opacity-40">
              Undo
            </button>
            <button onClick={redo} disabled={redoStack.length === 0} className="px-2 py-1 text-xs border border-gray-300 rounded disabled:opacity-40">
              Redo
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="ml-auto px-3 py-1.5 text-xs bg-emerald-600 text-white rounded-md hover:bg-emerald-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save annotation revision'}
            </button>
          </div>
        )}
        {error && <p className="text-xs text-red-600 mb-2">{error}</p>}

        <canvas
          ref={canvasRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          className="w-full border border-gray-200 rounded cursor-crosshair"
        />
      </div>
    </div>
  )
}
