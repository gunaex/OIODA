// Owner action completion and impact resolution are deliberately separate.
export function impactResolutionFromActionResult(result) {
  return result?.impact_resolution || null;
}
