import click
from flask import Flask
from src.config import Config
from src.extensions import db, celery, migrate
from src.domain.models import Employee, Survey, Response, Department
from src.application.services.ingestion import IngestionService
from src.application.tasks.background import async_ingest_data
from src.application.tasks.ai_tasks import async_analyze_batch
from src.interface.api.routes import api_bp


def create_app(test_config=None):
    app = Flask(__name__)
    if test_config is None:
        # Load from .env / config.py (Production/Dev)
        app.config.from_object(Config)
    else:
        # Load from test_config passed by Pytest
        app.config.from_mapping(test_config)

    # Initialize Extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Configure Celery
    celery.conf.update(app.config)

    app.register_blueprint(api_bp)

    @app.cli.command("ingest-csv")
    @click.argument("file_path")
    def ingest_csv(file_path):
        try:
            IngestionService.process_data(source_url=file_path, force_local=True)
            print("Done.")
        except Exception as e:
            print(e)

    @app.cli.command("trigger-ingestion")
    def trigger_ingestion():
        """Triggers the Celery task to ingest data from GitHub."""
        task = async_ingest_data.delay()
        print(f"Task triggered! ID: {task.id}")

    @app.cli.command("trigger-ai")
    def trigger_ai():
        """Triggers the AI Sentiment Analysis Batch Job."""
        print("Triggering AI Analysis background task...")
        task = async_analyze_batch.delay()
        print(f"Task started! ID: {task.id}")
        print("Check worker logs for progress.")

    # Healthcheck
    @app.route('/health')
    def health():
        return {"status": "ok", "service": "web"}

    return app