import pytest
from unittest.mock import patch
from datetime import date
from src.domain.models import Employee, Department, Survey, Response, ResponseSentiment


class TestApiEndpoints:
    """
    Level 3 Tests: API Integration.
    Consolidates basic connectivity checks, schema validation (using sample_data),
    and complex logic verification (filtering, pagination, error handling).
    """

    # --- System & Health ---

    def test_health_check(self, client):
        """Check if the app is up and running."""
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json == {"status": "ok", "service": "web"}

    # --- Endpoint: /employees ---

    def test_list_employees_pagination_logic(self, client, db_session):
        """
        GIVEN a database with 15 employees
        WHEN GET /api/v1/employees is called without params
        THEN it should return the first page with default limit (10 items)
        """
        # 1. Arrange
        dept = Department(name="Engineering")
        db_session.add(dept)
        db_session.flush()

        # Create 15 employees
        employees = [
            Employee(name=f"Dev {i}", email=f"dev{i}@test.com", department_id=dept.id)
            for i in range(15)
        ]
        db_session.add_all(employees)
        db_session.commit()

        # 2. Act
        response = client.get('/api/v1/employees')

        # 3. Assert - Pagination Math
        assert response.status_code == 200
        data = response.json

        assert data['total'] == 15
        assert data['page'] == 1
        assert data['per_page'] == 10  # Default
        assert len(data['items']) == 10
        assert data['pages'] == 2

    def test_list_employees_schema_integrity(self, client, sample_data):
        """
        GIVEN the sample_data fixture (1 employee in 'Tech')
        WHEN GET /api/v1/employees is called
        THEN it should return correct nested structure (Department Name)
        """
        # 1. Act
        response = client.get('/api/v1/employees?page=1&per_page=10')

        # 2. Assert - Data Integrity
        assert response.status_code == 200
        data = response.json

        assert "items" in data
        assert data["total"] == 1
        assert data["items"][0]["email"] == "test@pin.com"
        # Check if Department relationship is loaded (Nested schema)
        assert data["items"][0]["department"]["name"] == "Tech"

    def test_list_employees_filtering(self, client, db_session):
        """
        GIVEN employees in different departments and roles
        WHEN GET /api/v1/employees is called with filters
        THEN it should return only matching records
        """
        # 1. Arrange
        dept_it = Department(name="IT")
        dept_hr = Department(name="HR")
        db_session.add_all([dept_it, dept_hr])
        db_session.flush()

        e1 = Employee(name="Alice", email="alice@test.com", department_id=dept_it.id, role="Developer")
        e2 = Employee(name="Bob", email="bob@test.com", department_id=dept_hr.id, role="Recruiter")
        e3 = Employee(name="Charlie", email="charlie@test.com", department_id=dept_it.id, role="Manager")
        db_session.add_all([e1, e2, e3])
        db_session.commit()

        # 2. Act: Filter by Dept IT and Role 'Dev' (partial match)
        response = client.get(f'/api/v1/employees?department_id={dept_it.id}&role=Dev')

        # 3. Assert
        assert response.status_code == 200
        data = response.json

        assert data['total'] == 1
        assert data['items'][0]['name'] == "Alice"

    # --- Endpoint: /dashboard/company ---

    def test_dashboard_metrics_insufficient_data(self, client, sample_data):
        """
        GIVEN a database with employees but NO responses (sample_data)
        WHEN GET /api/v1/dashboard/company is called
        THEN it should return valid structure but 'Insufficient Data' classification
        """
        response = client.get('/api/v1/dashboard/company')

        assert response.status_code == 200
        data = response.json

        assert "company_enps" in data
        assert data["total_employees"] == 1  # Created in fixture
        assert data["company_enps"]["classification"] == "Insufficient Data"
        assert data["participation_rate"] == 0.0

    def test_get_company_metrics_success(self, client, db_session):
        """
        GIVEN a database with survey responses
        WHEN GET /api/v1/dashboard/company is called
        THEN it should return calculated eNPS and participation rate
        """
        # 1. Arrange
        survey = Survey(date=date(2023, 1, 1), name="Test Survey")
        db_session.add(survey)
        db_session.flush()

        emp = Employee(name="Test", email="t@t.com")
        db_session.add(emp)
        db_session.flush()

        # Add a Promoter Response (10)
        resp = Response(employee_id=emp.id, survey_id=survey.id, enps=10)
        db_session.add(resp)
        db_session.commit()

        # 2. Act
        response = client.get('/api/v1/dashboard/company')

        # 3. Assert
        assert response.status_code == 200
        data = response.json

        # Structure from DashboardStats schema
        assert data['total_employees'] == 1
        assert data['participation_rate'] == 100.0

        enps = data['company_enps']
        assert enps['score'] == 100  # 100% Promoters - 0% Detractors
        assert enps['classification'] == "Excellent"

    # --- Endpoint: /departments ---

    def test_list_departments(self, client, db_session):
        """
        GIVEN multiple departments
        WHEN GET /api/v1/departments is called
        THEN it should return a list sorted by name
        """
        # 1. Arrange (Insert out of order)
        d1 = Department(name="Sales")
        d2 = Department(name="Admin")
        db_session.add_all([d1, d2])
        db_session.commit()

        # 2. Act
        response = client.get('/api/v1/departments')

        # 3. Assert
        assert response.status_code == 200
        data = response.json

        assert len(data) == 2
        assert data[0]['name'] == "Admin"  # Sorted A-Z
        assert data[1]['name'] == "Sales"

    # --- Endpoint: /analytics/sentiment-overview ---

    def test_get_sentiment_overview_success(self, client, db_session):
        """
        GIVEN response sentiments exist
        WHEN GET /api/v1/analytics/sentiment-overview is called
        THEN it should return aggregated metrics structure
        """
        # 1. Arrange
        emp = Employee(name="User", email="u@u.com")
        survey = Survey(date=date(2023, 1, 1))
        db_session.add_all([emp, survey])
        db_session.flush()

        resp = Response(employee_id=emp.id, survey_id=survey.id)
        db_session.add(resp)
        db_session.flush()

        # Add sentiment
        sentiment = ResponseSentiment(
            response_id=resp.id,
            field_name='manager_interaction_comment',
            sentiment_label='POSITIVE',
            sentiment_score=0.9,
            sentiment_rating=5
        )
        db_session.add(sentiment)
        db_session.commit()

        # 2. Act
        response = client.get('/api/v1/analytics/sentiment-overview')

        # 3. Assert
        assert response.status_code == 200
        data = response.json

        # Check top level
        assert 'metrics' in data
        item = data['metrics'][0]

        # Check SentimentMetric schema structure
        assert item['field_name'] == 'manager_interaction_comment'
        assert item['friendly_label'] == 'Manager Bond'
        assert item['average_rating'] == 5.0
        assert item['sample_size'] == 1
        assert item['distribution']['POSITIVE'] == 1

    @patch('src.application.services.analytics.AnalyticsService.get_sentiment_overview')
    def test_get_sentiment_overview_error_handling(self, mock_service, client):
        """
        GIVEN an unexpected error in the Service layer
        WHEN GET /api/v1/analytics/sentiment-overview is called
        THEN it should return 500 status code and clean JSON error
        """
        # 1. Arrange: Mock the service to raise Exception
        mock_service.side_effect = Exception("Database Connection Failed")

        # 2. Act
        response = client.get('/api/v1/analytics/sentiment-overview')

        # 3. Assert
        assert response.status_code == 500
        data = response.json
        assert data['error'] == "Failed to calculate sentiment metrics"