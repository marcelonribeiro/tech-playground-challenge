from src.extensions import celery, db
from src.domain.models import Response
from src.application.services.sentiment import SentimentAnalysisService
import logging

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def async_analyze_batch(self):
    """
    Batch processing task.
    Fetches all Response IDs and triggers analysis for each one.

    Senior Note: In a massive scale scenario, we would use pagination (offset/limit)
    or a cursor to fetch IDs, but for this dataset size, fetching IDs is safe.
    """
    logger.info("Task: Starting Batch Sentiment Analysis...")

    try:
        # Fetch only IDs (lightweight query)
        all_response_ids = [r.id for r in db.session.query(Response.id).all()]
        total = len(all_response_ids)
        logger.info(f"Task: Found {total} responses to analyze.")

        success_count = 0
        error_count = 0

        for index, resp_id in enumerate(all_response_ids):
            try:
                # Call the service synchronously for each item in the worker process
                SentimentAnalysisService.analyze_response(resp_id)
                success_count += 1

                # Log progress every 10%
                if total > 0 and index % (max(1, total // 10)) == 0:
                    logger.info(f"Task: Progress {index}/{total} ({round(index / total * 100)}%)")

            except Exception as e:
                error_count += 1
                logger.error(f"Task: Failed to analyze ID {resp_id}. Error: {e}")
                continue

        return f"Batch Complete. Success: {success_count}, Errors: {error_count}"

    except Exception as fatal_error:
        logger.critical(f"Task: Fatal error in batch execution: {fatal_error}")
        raise fatal_error