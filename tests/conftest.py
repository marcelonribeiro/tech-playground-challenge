import pytest
from datetime import date
from src.app import create_app
from src.extensions import db
from src.domain.models import Employee, Department, Survey, Response


@pytest.fixture(scope='session')
def app():
    """
    Creates a Flask app context for tests.
    Passes test_config to force SQLite and override environment variables.
    """
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://"
    }

    app = create_app(test_config=test_config)

    yield app


@pytest.fixture(scope='function')
def client(app):
    """
    A test client for the app.
    """
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """
    A test runner for the app's CLI commands.
    """
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def db_session(app):
    """
    Creates a fresh database for each test function.
    Create tables -> Run Test -> Drop tables.
    """
    with app.app_context():
        db.create_all()

        # Populate minimal generic data if needed here

        yield db.session

        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_data(db_session):
    """
    Fixture to populate the DB with a controlled scenario for Analytics tests.
    """
    # 1. Department
    dept = Department(name="Tech")
    db_session.add(dept)
    db_session.flush()

    # 2. Employee
    emp = Employee(name="Tester", email="test@pin.com", department_id=dept.id)
    db_session.add(emp)
    db_session.flush()

    # 3. Survey
    survey = Survey(date=date(2022, 1, 1), name="Test Survey")
    db_session.add(survey)
    db_session.flush()

    return {"dept": dept, "emp": emp, "survey": survey}