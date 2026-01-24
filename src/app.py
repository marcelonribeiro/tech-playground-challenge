import click
from flask import Flask
from src.config import Config
from src.extensions import db, celery
from src.domain.models import Employee, Survey, Response, Department
from src.application.services.ingestion import IngestionService
from src.application.tasks.background import async_ingest_data
from src.interface.api.routes import api_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize Extensions
    db.init_app(app)

    # Configure Celery
    celery.conf.update(app.config)

    app.register_blueprint(api_bp)

    @app.cli.command("db-init")
    def db_init():
        """Initialize the database (Create Tables)."""
        db.create_all()
        print("Database initialized successfully.")

    @app.cli.command("trigger-ingestion")
    def trigger_ingestion():
        """Triggers the Celery task to ingest data from GitHub."""
        task = async_ingest_data.delay()
        print(f"Task triggered! ID: {task.id}")

    # Healthcheck
    @app.route('/health')
    def health():
        return {"status": "ok", "service": "web"}

    return app