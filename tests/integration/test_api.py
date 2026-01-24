from src.domain.models import Employee


def test_health_check(client):
    """Check if the app is up."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {"status": "ok", "service": "web"}


def test_get_employees_pagination(client, db_session, sample_data):
    """
    GIVEN a database with 1 employee
    WHEN GET /api/v1/employees is called
    THEN it should return paginated data
    """
    response = client.get('/api/v1/employees?page=1&per_page=10')

    assert response.status_code == 200
    data = response.json

    assert "items" in data
    assert data["total"] == 1
    assert data["items"][0]["email"] == "test@pin.com"
    # Check if Department relationship is loaded (Nested schema)
    assert data["items"][0]["department"]["name"] == "Tech"


def test_dashboard_metrics(client, db_session, sample_data):
    """
    GIVEN an empty database (from sample_data fixture only having setup data)
    WHEN GET /api/v1/dashboard/company is called
    THEN it should return zeroed metrics but valid structure
    """
    response = client.get('/api/v1/dashboard/company')

    assert response.status_code == 200
    data = response.json

    assert "company_enps" in data
    assert data["total_employees"] == 1  # Created in fixture
    assert data["company_enps"]["classification"] == "Insufficient Data"