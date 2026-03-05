"""S3-compatible Uploader Implementation."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from .base import UploaderBackend, UploadError

logger = logging.getLogger(__name__)


class S3Uploader(UploaderBackend):
    """Uploads images to AWS S3, DigitalOcean Spaces, Cloudflare R2, MinIO, etc."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket_name: str | None = None,
        public_url_format: str | None = None,
    ):
        """Initialize with S3 credentials from settings.

        Args:
            endpoint_url: Set this for non-AWS hosts (e.g., Cloudflare R2).
            access_key: The IAM Access Key.
            secret_key: The IAM Secret Key.
            bucket_name: The destination bucket.
            public_url_format: How to format the final public URL. 
                               E.g., "https://my-cdn.com/{bucket}/{key}"
        """
        if not all([access_key, secret_key, bucket_name]):
            raise UploadError("S3 uploader requires access_key, secret_key, and bucket_name in settings.")

        self.bucket_name = bucket_name
        self.public_url_format = public_url_format or "https://{bucket}.s3.amazonaws.com/{key}"
        
        try:
            import boto3
        except ImportError:
            raise UploadError("S3 uploading requires the `boto3` package. Install with: pip install shotx[s3]")

        try:
            # We explicitly pass the endpoint_url so it works with any S3-compatible service
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint_url if endpoint_url else None,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        except Exception as e:
            raise UploadError(f"Failed to initialize S3 client: {e}")

    def upload(self, file_path: Path) -> str:
        if not file_path.exists():
            raise UploadError(f"File not found: {file_path}")

        # ShareX default behavior is usually Year/Month/filename, but 
        # for MVP we can just drop it in the root or an 'images/' prefix.
        object_name = f"images/{file_path.name}"
        
        # Determine content type dynamically
        mime_type, _ = mimetypes.guess_type(file_path.name)
        content_type = mime_type or "application/octet-stream"

        extra_args = {
            "ContentType": content_type,
            # Normally S3 requires ACL 'public-read' but many modern buckets 
            # enforce Block Public Access and rely on bucket policies. 
            # However, ShareX historically tries to set public-read.
            # We omit ACL here assuming the user's bucket/CDN policy handles it cleanly,
            # or we could make it configurable. 
        }

        logger.info("Uploading %s to s3://%s/%s ...", file_path.name, self.bucket_name, object_name)

        try:
            self.s3_client.upload_file(
                str(file_path), 
                self.bucket_name, 
                object_name,
                ExtraArgs=extra_args
            )
        except Exception as e:
            # Catching Exception because botocore isn't imported at module level
            from botocore.exceptions import BotoCoreError, ClientError
            if isinstance(e, (BotoCoreError, ClientError)):
                logger.error("S3 upload failed: %s", e)
                raise UploadError(f"Failed to upload to S3: {e}")
            raise

        # Construct the final public URL
        link = self.public_url_format.format(
            bucket=self.bucket_name,
            key=object_name,
        )
        
        logger.info("S3 upload successful: %s", link)
        return link
