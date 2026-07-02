"""
Job Queue Service
------------------
Thin wrapper around arq's Redis connection pool, used by the API process
to enqueue jobs. The actual job execution happens in the separate worker
process (see worker.py / tasks.py).
"""
import os
import logging
from typing import Optional

from arq import create_pool
from arq.connections import RedisSettings, ArqRedis

logger = logging.getLogger(__name__)

_pool: Optional[ArqRedis] = None


def _redis_settings() -> RedisSettings:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return RedisSettings.from_dsn(redis_url)


async def get_pool() -> ArqRedis:
    """Get or create the shared arq Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())
        logger.info("arq Redis pool created")
    return _pool


async def enqueue_process_document(
    doc_id: str,
    file_path: str,
    original_filename: str,
    user_id: Optional[str] = None,
) -> str:
    """Enqueue a document-processing job. Returns the arq job_id."""
    pool = await get_pool()
    job = await pool.enqueue_job(
        "process_document_task",
        doc_id,
        file_path,
        original_filename,
        user_id,
        _job_id=f"process_{doc_id}",  # deterministic ID -> natural dedup on retry
    )
    return job.job_id if job else f"process_{doc_id}"