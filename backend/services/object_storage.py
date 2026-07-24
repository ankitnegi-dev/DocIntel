"""
Object Storage Service
-----------------------
S3-compatible client for Backblaze B2 (or any S3-compatible provider).
Replaces local disk storage for uploaded files and rendered page images.
"""
import os
import logging
from io import BytesIO

import boto3
from botocore.client import Config

logger = logging.getLogger(__name__)

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=os.getenv("B2_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("B2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("B2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )
        logger.info("Object storage client initialized")
    return _client


BUCKET = os.getenv("B2_BUCKET_NAME", "docintel-storage")


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
    """Upload raw bytes to object storage under the given key."""
    try:
        client = _get_client()
        client.put_object(Bucket=BUCKET, Key=key, Body=data, ContentType=content_type)
        return True
    except Exception as e:
        logger.error(f"Upload failed for key {key}: {e}")
        raise


def download_bytes(key: str) -> bytes | None:
    """Download an object's bytes. Returns None if not found."""
    try:
        client = _get_client()
        response = client.get_object(Bucket=BUCKET, Key=key)
        return response["Body"].read()
    except client.exceptions.NoSuchKey:
        return None
    except Exception as e:
        logger.error(f"Download failed for key {key}: {e}")
        return None


def delete_object(key: str) -> bool:
    """Delete an object by key."""
    try:
        client = _get_client()
        client.delete_object(Bucket=BUCKET, Key=key)
        return True
    except Exception as e:
        logger.error(f"Delete failed for key {key}: {e}")
        return False


def delete_objects_with_prefix(prefix: str) -> int:
    """Delete all objects whose key starts with the given prefix. Returns count deleted."""
    try:
        client = _get_client()
        paginator = client.get_paginator("list_objects_v2")
        deleted = 0
        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
            objects = page.get("Contents", [])
            if not objects:
                continue
            keys = [{"Key": obj["Key"]} for obj in objects]
            client.delete_objects(Bucket=BUCKET, Delete={"Objects": keys})
            deleted += len(keys)
        return deleted
    except Exception as e:
        logger.error(f"Prefix delete failed for {prefix}: {e}")
        return 0


def object_exists(key: str) -> bool:
    """Check if an object exists without downloading it."""
    try:
        client = _get_client()
        client.head_object(Bucket=BUCKET, Key=key)
        return True
    except Exception:
        return False

def persist_document_files(doc_id: str, file_path, page_count: int, pages_dir) -> None:
    """
    Upload a document's original file and all rendered page images to object
    storage, then remove the local copies. Best-effort: logs but does not
    raise on failure, since the document is already indexed and usable even
    if this durability step fails.
    Shared by the upload job (tasks.py) and manual reindex (routers/documents.py)
    so there's one implementation instead of two copies that can drift apart.
    """
    from pathlib import Path
    file_path = Path(file_path)
    pages_dir = Path(pages_dir)

    try:
        if file_path.exists():
            content = file_path.read_bytes()
            key = f"originals/{file_path.name}"
            upload_bytes(key, content)
            file_path.unlink()
    except Exception as e:
        logger.warning(f"Failed to persist original file for {doc_id} to object storage: {e}")

    for page_num in range(1, page_count + 1):
        local_image = pages_dir / f"{doc_id}_{page_num}.png"
        if not local_image.exists():
            continue
        try:
            content = local_image.read_bytes()
            key = f"pages/{doc_id}_{page_num}.png"
            upload_bytes(key, content, content_type="image/png")
            local_image.unlink()
        except Exception as e:
            logger.warning(f"Failed to persist page image {page_num} for {doc_id}: {e}")