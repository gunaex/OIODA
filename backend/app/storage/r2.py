import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from .base import EvidenceStorage


class R2EvidenceStorage(EvidenceStorage):
    """Cloudflare R2 via its S3-compatible API — see ADR-0002. R2
    Standard storage class only (never Infrequent Access — requirement
    11); StorageClass is deliberately never set to anything but the
    implicit/explicit Standard default."""

    def __init__(
        self,
        account_id: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None = None,
    ):
        # endpoint_url override exists only for tests (pointing at a local
        # mock S3 server) — production always derives it from account_id.
        self.bucket_name = bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            # R2 has no regions; "auto" is Cloudflare's documented value.
            region_name="auto",
            config=BotoConfig(signature_version="s3v4"),
        )

    def put(self, key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=content,
            ContentType=content_type,
            StorageClass="STANDARD",
        )

    def get(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket_name, Key=key)

    def presigned_get_url(self, key: str, expires_in: int = 300) -> str | None:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )
