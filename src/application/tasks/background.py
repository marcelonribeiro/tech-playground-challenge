from src.extensions import celery
from src.application.services.ingestion import IngestionService
import logging

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3)
def async_ingest_data(self, url: str = None, force_local: bool = False):
    """
    Background task to update the database from the source CSV.
    Retries automatically on network failure.

    Args:
        url (str, optional): Custom URL to fetch data from. Defaults to Service default.
        force_local (bool): If True, skips download and uses local backup immediately.
    """
    target_url = url or IngestionService.DEFAULT_URL

    logger.info(f"Task: Starting async ingestion. Target: {target_url}, Force Local: {force_local}")

    try:
        # Calls the updated Service method with correct signature
        IngestionService.process_data(source_url=target_url, force_local=force_local)
        return "Ingestion Successful"

    except Exception as exc:
        logger.error(f"Task failed: {exc}")
        # Exponential backoff retry: 60s, 120s, 240s...
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))