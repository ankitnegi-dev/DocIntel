"""
arq Worker Settings
--------------------
Defines the background job queue worker. Runs as a separate process from
the FastAPI app (see docker-compose.yml `worker` service), so uploads
survive API server restarts/redeploys - the job lives in Redis until a
worker picks it up, not in the API process's memory.
"""
import os
import logging
from arq.connections import RedisSettings

from tasks import process_document_task

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _redis_settings() -> RedisSettings:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return RedisSettings.from_dsn(redis_url)


async def startup(ctx):
    logger.info("arq worker starting up...")


async def shutdown(ctx):
    logger.info("arq worker shutting down...")


class WorkerSettings:
    functions = [process_document_task]
    redis_settings = _redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 4              # how many jobs this worker processes concurrently
    job_timeout = 600         # 10 minutes max per job (generous for slow OCR/model downloads)
    keep_result = 3600        # keep job results for 1 hour (for status lookups)