#!/usr/bin/env python
"""Real Cloudflare R2 staging smoke test — requirement 6.

The moto-based tests in tests/test_r2_storage.py prove R2EvidenceStorage's
boto3 calls are wired up correctly against an S3-compatible API. They do
NOT prove the actual R2 endpoint, real credentials, real bucket
permissions, or real network path work — only a live run against real R2
can prove that. This script is that live run. It is NOT part of the
pytest suite (it needs real secrets and network access that CI/local dev
don't have) — run it manually, once, before the first production
release, and again after any R2 credential/bucket change.

Usage:
    cd backend
    R2_ACCOUNT_ID=... R2_BUCKET_NAME=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
        python scripts/r2_staging_smoke_test.py

Exits non-zero on any failure, with the specific step that failed.
"""
import hashlib
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.r2 import R2EvidenceStorage  # noqa: E402

REQUIRED_VARS = ["R2_ACCOUNT_ID", "R2_BUCKET_NAME", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"]


def fail(step: str, exc: Exception | None = None):
    print(f"FAILED at: {step}")
    if exc:
        print(f"  {type(exc).__name__}: {exc}")
    sys.exit(1)


def main():
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}")
        print("This script talks to a REAL Cloudflare R2 bucket — see docs/DEPLOYMENT.md for setup.")
        sys.exit(2)

    storage = R2EvidenceStorage(
        account_id=os.environ["R2_ACCOUNT_ID"],
        bucket_name=os.environ["R2_BUCKET_NAME"],
        access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )

    test_key = f"evidence/_r2-smoke-test/{int(time.time())}/smoke.png"
    # A genuinely valid tiny PNG (same construction as tests/conftest.py).
    import struct
    import zlib

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    content = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff\x00\x00" * 4))
        + chunk(b"IEND", b"")
    )
    expected_sha256 = hashlib.sha256(content).hexdigest()

    print(f"1. PUT {test_key} ...")
    try:
        storage.put(test_key, content, "image/png")
    except Exception as exc:
        fail("put_object (check R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY and bucket permissions)", exc)
    print("   ok")

    print("2. HEAD (exists) ...")
    try:
        if not storage.exists(test_key):
            fail("exists() returned False immediately after a successful put")
    except Exception as exc:
        fail("head_object", exc)
    print("   ok")

    print("3. GET (byte-for-byte roundtrip + checksum) ...")
    try:
        fetched = storage.get(test_key)
    except Exception as exc:
        fail("get_object", exc)
    if fetched != content:
        fail("get_object returned different bytes than were put")
    if hashlib.sha256(fetched).hexdigest() != expected_sha256:
        fail("sha256 mismatch after roundtrip")
    print("   ok")

    print("4. Presigned GET URL — actually fetch it over HTTP (proves the real endpoint/signing, not just that a URL string was generated) ...")
    try:
        url = storage.presigned_get_url(test_key, expires_in=60, response_filename="smoke-test.png", response_content_type="image/png")
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = resp.read()
            disposition = resp.headers.get("Content-Disposition", "")
    except Exception as exc:
        fail("presigned URL fetch over real HTTP", exc)
    if body != content:
        fail("presigned URL returned different bytes than were put")
    if "smoke-test.png" not in disposition:
        fail(f"Content-Disposition override didn't apply — got: {disposition!r}")
    print("   ok")

    print("5. DELETE (cleanup) ...")
    try:
        storage.delete(test_key)
        if storage.exists(test_key):
            fail("object still exists after delete")
    except Exception as exc:
        fail("delete_object", exc)
    print("   ok")

    print("\nALL CHECKS PASSED — real R2 endpoint, credentials, upload, presigned download, and retrieval all confirmed working.")


if __name__ == "__main__":
    main()
