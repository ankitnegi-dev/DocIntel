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