from datetime import timedelta

import click
import os

from celery.schedules import crontab
from flask import Flask

from src.config import Config
from src.extensions import db, celery, migrate
from src.application.services.ingestion import IngestionService
from src.interface.api.routes import api_bp
from src.interface.web import web_bp


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

    celery_config = {
        'broker_url': os.environ.get('CELERY_BROKER_URL'),
        'result_backend': os.environ.get('CELERY_RESULT_BACKEND'),
        'task_ignore_result': True,
        'broker_connection_retry_on_startup': True,
        'beat_schedule': {
            'daily-ingestion-pipeline': {
                'task': 'data_pipeline.run_full_sync',
                'schedule': crontab(hour=0, minute=0),
            },
        }
    }

    if app.config.get('TESTING'):
        celery_config['task_always_eager'] = True
        celery_config['task_eager_propagates'] = True

    celery.conf.update(**celery_config)

    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    @app.cli.command("bootstrap")
    def bootstrap():
        """
        Runs the unified data pipeline (Ingestion + AI).
        Ensures the database is fully seeded and analyzed in one go.
        """
        print("--- BOOTSTRAP: STARTING ---")

        try:
            print("1. Running Unified Data Pipeline (ETL + AI)...")
            stats = IngestionService.run_pipeline()
            count = stats.get('processed', 0)
            print(f"   -> Success! Records processed: {count}")
            print(f"   -> AI Analysis: {stats.get('ai_analyzed', 0)}")
        except Exception as e:
            print(f"   -> Critical Error during bootstrap: {e}")
            import sys
            sys.exit(1)

        print("--- BOOTSTRAP: FINISHED ---")

    # Healthcheck
    @app.route('/health')
    def health():
        return {"status": "ok", "service": "web"}

    return app