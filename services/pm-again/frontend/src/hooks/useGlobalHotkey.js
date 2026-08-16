import { useEffect } from 'react'

const FORM_TAGS = ['INPUT', 'TEXTAREA', 'SELECT']

/** Fires `callback` on a global keydown matching `key` (e.g. "/", "n", "Escape"),
 * skipping keystrokes typed into form fields unless `allowInFormTags` is set —
 * react-hotkeys-hook v5's own binding silently no-ops in this app (confirmed:
 * the raw keydown reaches the page, but the library's handler never fires),
 * so shortcuts are wired directly instead.
 * Pass `ctrlOrCmd: true` to require Ctrl (Win/Linux) or Cmd (Mac) held down —
 * useful for chords like Ctrl/Cmd+K that must work while typing elsewhere. */
export default function useGlobalHotkey(
  key,
  callback,
  { allowInFormTags = false, ctrlOrCmd = false } = {},
) {
  useEffect(() => {
    const handler = (e) => {
      if (e.key.toLowerCase() !== key.toLowerCase()) return
      if (ctrlOrCmd && !(e.metaKey || e.ctrlKey)) return
      const tag = document.activeElement?.tagName
      if (!allowInFormTags && FORM_TAGS.includes(tag)) return
      callback(e)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [key, callback, allowInFormTags, ctrlOrCmd])
}
