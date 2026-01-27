from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()
celery = Celery(__name__)