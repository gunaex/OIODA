// Pure helpers behind the note editor/preview. Kept out of the .jsx files so
// they can be exercised on their own — these two regex passes are where the
// `#tag` / `[[wiki-link]]` behaviour actually lives.

// One combined pass, so a rewritten link's own text can't be re-matched by
// the next rule (an entity titled "Fix #123" would otherwise grow a tag).
const TOKEN_RE = /\[\[([^[\]]+)\]\]|#([0-9A-Za-z_\-฀-๿]+)/g
// Fenced blocks and inline code are passed through untouched, so a literal
// `#tag` in a code sample stays a code sample.
const CODE_RE = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/

export const TAG_CHAR_RE = /[0-9A-Za-z_\-฀-๿]/

// Angle-bracket link destinations, so a link body containing ( or ) can't
// break out of the href.
const href = (target) => `<pmx:${target}>`
const escapeLinkText = (text) => String(text).replace(/([[\]])/g, '\\$1')

function rewriteSegment(text, linkMap) {
  return text.replace(TOKEN_RE, (match, body, tag) => {
    if (tag !== undefined) return `[#${tag}](${href(`tag/${tag.toLowerCase()}`)})`
    const link = linkMap.get(body.trim())
    if (!link || !link.resolved) return `[${escapeLinkText(body)}](${href('dead')})`
    return `[${escapeLinkText(link.label)}](${href(`${link.target_type}/${link.target_id}`)})`
  })
}

/** Rewrites `#tag` and `[[link]]` into ordinary markdown links carrying a
 *  private `pmx:` href, which NoteMarkdown's custom `a` renderer turns into
 *  pills / navigation buttons / greyed-out dead links. */
export function linkifyMarkdown(markdown, links = []) {
  if (!markdown) return ''
  const linkMap = new Map(links.map((l) => [l.raw, l]))
  return markdown
    .split(CODE_RE)
    .map((segment, i) => (i % 2 === 1 ? segment : rewriteSegment(segment, linkMap)))
    .join('')
}

/** Finds the `#partial` the caret currently sits inside, if any — drives the
 *  quick-hashtag autocomplete. Returns null when the caret isn't in a tag. */
export function activeTagFragment(text, caret) {
  let i = caret
  while (i > 0 && TAG_CHAR_RE.test(text[i - 1])) i -= 1
  if (i === 0 || text[i - 1] !== '#') return null
  // `a#b` is not a tag — the '#' has to start a word.
  if (i - 1 > 0 && TAG_CHAR_RE.test(text[i - 2])) return null
  return { start: i - 1, query: text.slice(i, caret).toLowerCase() }
}
