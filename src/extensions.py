from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()

def make_celery(app_name=__name__):
    return Celery(app_name)

celery = make_celery()