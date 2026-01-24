from src.app import create_app
from src.extensions import celery

app = create_app()
app.app_context().push()