import { useEffect } from 'react'

const FORM_TAGS = ['INPUT', 'TEXTAREA', 'SELECT']

/** Fires `callback` on a global keydown matching `key` (e.g. "/", "n", "Escape"),
 * skipping keystrokes typed into form fields unless `allowInFormTags` is set —
 * react-hotkeys-hook v5's own binding silently no-ops in this app (confirmed:
 * the raw keydown reaches the page, but the library's handler never fires),
 * so shortcuts are wired directly instead. */
export default function useGlobalHotkey(key, callback, { allowInFormTags = false } = {}) {
  useEffect(() => {
    const handler = (e) => {
      if (e.key !== key) return
      const tag = document.activeElement?.tagName
      if (!allowInFormTags && FORM_TAGS.includes(tag)) return
      callback(e)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [key, callback, allowInFormTags])
}
