from src.extensions import celery
from src.application.services.ingestion import IngestionService

@celery.task(
    name='data_pipeline.run_full_sync',
    bind=True,  # Access to 'self'
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    retry_jitter=True
)
def run_full_data_sync(self):
    """
    Background task to run the complete ETL + AI pipeline.
    Scheduled to run periodically (Daily)
    Includes retry logic for robustness against network/DB blips.
    """
    print(f"I [Celery] Starting Full Data Sync Task (Try {self.request.retries + 1})...")

    try:
        result = IngestionService.run_pipeline()

        msg = f"Pipeline completed. Stats: {result}"
        print(f"I [Celery] {msg}")
        return msg

    except Exception as e:
        print(f"E [Celery] Pipeline failed: {str(e)}")
        raise e