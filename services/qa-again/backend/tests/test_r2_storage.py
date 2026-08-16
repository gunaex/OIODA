"""Unit tests for the R2 backend against a local mock S3 server (moto's
ThreadedMotoServer) — proves the S3-compatible calls (put/get/exists/
delete/presigned URL) are wired up correctly without needing real
Cloudflare R2 credentials or network access. A real HTTP server is used
(rather than moto's `@mock_aws` interceptor) because that interceptor
only recognizes AWS's own endpoint patterns, not R2's custom domain —
exactly the kind of "custom endpoint_url" case R2EvidenceStorage exists
to handle, so the test fixture uses the same mechanism for real."""

import boto3
import pytest
from moto.server import ThreadedMotoServer

from app.storage.r2 import R2EvidenceStorage

BUCKET = "qa-again-evidence-test"


@pytest.fixture(scope="module")
def moto_endpoint():
    server = ThreadedMotoServer(port=0)
    server.start()
    _host, port = server.get_host_and_port()
    # moto binds "0.0.0.0" (all interfaces) but that's not a connectable
    # address as a client target on every platform — connect to loopback.
    yield f"http://127.0.0.1:{port}"
    server.stop()


@pytest.fixture
def r2(moto_endpoint):
    setup_client = boto3.client(
        "s3",
        endpoint_url=moto_endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    setup_client.create_bucket(Bucket=BUCKET)

    storage = R2EvidenceStorage(
        account_id="unused-when-endpoint_url-is-set",
        bucket_name=BUCKET,
        access_key_id="test",
        secret_access_key="test",
        endpoint_url=moto_endpoint,
    )
    yield storage


def test_put_get_roundtrip(r2):
    r2.put("evidence/proj/1/abc.png", b"hello world", "image/png")
    assert r2.get("evidence/proj/1/abc.png") == b"hello world"


def test_exists(r2):
    assert r2.exists("evidence/proj/1/missing.png") is False
    r2.put("evidence/proj/1/present.png", b"x", "image/png")
    assert r2.exists("evidence/proj/1/present.png") is True


def test_delete(r2):
    r2.put("evidence/proj/1/gone.png", b"x", "image/png")
    assert r2.exists("evidence/proj/1/gone.png") is True
    r2.delete("evidence/proj/1/gone.png")
    assert r2.exists("evidence/proj/1/gone.png") is False


def test_presigned_url_is_generated_and_scoped_to_the_key(r2):
    r2.put("evidence/proj/1/shot.png", b"x", "image/png")
    url = r2.presigned_get_url("evidence/proj/1/shot.png", expires_in=60)
    assert url is not None
    assert "shot.png" in url
    assert "Signature" in url  # a real presigned URL, not a bare object URL


def test_standard_storage_class_is_used_not_infrequent_access(r2):
    """Requirement 11 — R2 Standard, never Infrequent Access."""
    r2.put("evidence/proj/1/std.png", b"x", "image/png")
    head = r2.client.head_object(Bucket=BUCKET, Key="evidence/proj/1/std.png")
    # S3/R2 omit StorageClass entirely for the default Standard tier.
    assert head.get("StorageClass", "STANDARD") == "STANDARD"
