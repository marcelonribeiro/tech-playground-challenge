from flask_sqlalchemy import SQLAlchemy
from celery import Celery

db = SQLAlchemy()

def make_celery(app_name=__name__):
    return Celery(app_name)

celery = make_celery()