"""Evidence file safety: MIME-signature sniffing and safe on-disk naming.

Deliberately no Pillow/image-processing dependency — sniffing magic bytes
covers the "don't trust the claimed content-type" requirement without a
new dependency; width/height/thumbnails are not built in Phase 5 (see
docs/ROADMAP.md). Screenshots only (no video, ever, per rebuild prompt
section 13).
"""

MAX_EVIDENCE_SIZE_BYTES = 8 * 1024 * 1024  # 8MB — screenshots, not video

_SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
]


def sniff_image(content: bytes) -> tuple[str, str] | None:
    """Returns (content_type, extension) based on the file's actual bytes,
    or None if it doesn't match a recognized image signature. WEBP is
    checked separately since its signature isn't a fixed leading prefix."""
    for signature, content_type, ext in _SIGNATURES:
        if content.startswith(signature):
            return content_type, ext
    if content[0:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None
