import { useState } from 'react'

/** Re-enter-your-password confirmation gate for consequential actions
 * (archiving/deleting a project) — mirrors the same re-auth check the
 * change-password flow already does server-side. */
export default function PasswordConfirmModal({ title, message, confirmLabel, danger, onConfirm, onCancel }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!password) return
    setError(null)
    setSubmitting(true)
    try {
      await onConfirm(password)
    } catch (err) {
      setError(err.response?.data?.detail || 'Incorrect password')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4" onClick={onCancel}>
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm bg-white rounded-lg shadow-2xl p-5"
      >
        <h3 className="font-semibold text-gray-900 mb-1">{title}</h3>
        <p className="text-sm text-gray-500 mb-4">{message}</p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Your current password"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
        <div className="flex justify-end gap-2 mt-4">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !password}
            className={`px-3 py-1.5 text-sm font-medium rounded-md text-white disabled:opacity-50 ${
              danger ? 'bg-red-600 hover:bg-red-700' : 'bg-indigo-600 hover:bg-indigo-700'
            }`}
          >
            {submitting ? 'Please wait…' : confirmLabel}
          </button>
        </div>
      </form>
    </div>
  )
}
