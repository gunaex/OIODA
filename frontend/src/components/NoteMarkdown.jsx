import { useMemo } from 'react'
import MDEditor from '@uiw/react-md-editor'
import { linkifyMarkdown } from './noteMarkdownUtils.js'

// Markdown preview for note pages: the library renders the markdown as
// normal, and we post-process the two syntaxes it doesn't know about —
// `#tag` and `[[wiki-link]]`.
//
// The post-processing happens *before* the markdown is parsed, by rewriting
// each occurrence into an ordinary markdown link with a private `pmx:` href.
// The custom `a` renderer below then turns those into a tag pill / an
// in-app navigation button / a greyed-out dead link. Doing it this way
// (rather than walking the rendered DOM) means everything the markdown
// parser already handles — code fences, escaping, nesting — keeps working.
// The rewrite itself lives in noteMarkdownUtils.js.

export default function NoteMarkdown({ source, links = [], onTagClick, onEntityClick }) {
  const rewritten = useMemo(() => linkifyMarkdown(source, links), [source, links])

  const components = useMemo(
    () => ({
      // `node` is react-markdown's AST node — pulled out of the spread so it
      // doesn't end up as a DOM attribute.
      a: ({ href: url, children, node: _node, ...props }) => {
        if (!url?.startsWith('pmx:')) {
          return (
            <a href={url} target="_blank" rel="noreferrer" {...props}>
              {children}
            </a>
          )
        }
        const target = url.slice('pmx:'.length)
        if (target === 'dead') {
          // Unresolved link: plain text, greyed, not clickable — never an error.
          return <span className="text-gray-400">[[{children}]]</span>
        }
        const [kind, id] = target.split('/')
        if (kind === 'tag') {
          return (
            <button
              type="button"
              onClick={() => onTagClick?.(id)}
              className="inline-block align-baseline px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-xs font-medium hover:bg-indigo-100"
            >
              {children}
            </button>
          )
        }
        return (
          <button
            type="button"
            onClick={() => onEntityClick?.(kind, Number(id))}
            className="text-indigo-600 underline hover:text-indigo-800"
          >
            {children}
          </button>
        )
      },
    }),
    [onTagClick, onEntityClick],
  )

  return (
    <div data-color-mode="light">
      <MDEditor.Markdown source={rewritten} components={components} style={{ background: 'transparent' }} />
    </div>
  )
}
