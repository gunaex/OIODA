// Where a resolved `[[wiki-link]]` should take you. Kept in one place so the
// Notes Hub, the preview renderer and the Linked Notes panels all agree.
//
// Task / Function / Board items have list pages rather than per-id detail
// routes, so those land on the list (the row is right there); notes and
// documents have a real detail view to open.
export function entityRoute(slug, kind, id) {
  switch (kind) {
    case 'note':
      return `/${slug}/notes-hub?note=${id}`
    case 'task':
      return `/${slug}/tasks`
    case 'function':
      return `/${slug}/functions`
    case 'document':
      return `/${slug}/documents/${id}`
    case 'board_item':
      return `/${slug}/board`
    default:
      return `/${slug}`
  }
}

export const ENTITY_LABELS = {
  note: 'Note',
  task: 'Task',
  function: 'Function',
  document: 'Document',
  board_item: 'Board Item',
}
