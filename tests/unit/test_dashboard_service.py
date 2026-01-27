import pytest
from datetime import date
from src.application.services.dashboard_service import DashboardService
from src.domain.models import Employee, Department, Survey, Response, ResponseSentiment
from src.extensions import db


@pytest.fixture
def dashboard_data(db_session):
    """
    Creates a controlled environment for testing metrics.
    Scenario:
    - Dept A (Engineering):
        - Emp 1: Promoter (10), High Feedback (5)
        - Emp 2: Detractor (0), Low Feedback (1)
        - Emp 3: Passive (8), Medium Feedback (3)
    - Dept B (HR):
        - Emp 4: Promoter (9), High Feedback (4)

    Calculations Expected:
    - Global eNPS:
        - Total: 4
        - Promoters: 2 (Emp 1, Emp 4) -> 50%
        - Detractors: 1 (Emp 2) -> 25%
        - Passives: 1 (Emp 3) -> 25%
        - Score: 50 - 25 = +25.0

    - Engineering eNPS:
        - Total: 3
        - Promoters: 1 (33.3%)
        - Detractors: 1 (33.3%)
        - Score: 0.0
    """
    # 1. Setup Structure
    dept_eng = Department(name="Engineering")
    dept_hr = Department(name="HR")
    db_session.add_all([dept_eng, dept_hr])
    db_session.flush()

    survey = Survey(date=date(2023, 1, 1), name="Test Survey")
    db_session.add(survey)
    db_session.flush()

    # 2. Employees
    employees = [
        Employee(name="Alice", email="alice@pin.com", department_id=dept_eng.id, role="Dev"),
        Employee(name="Bob", email="bob@pin.com", department_id=dept_eng.id, role="Dev"),
        Employee(name="Charlie", email="charlie@pin.com", department_id=dept_eng.id, role="Manager"),
        Employee(name="Diana", email="diana@pin.com", department_id=dept_hr.id, role="Recruiter"),
    ]
    db_session.add_all(employees)
    db_session.flush()

    # 3. Responses (Quantitative)
    responses = [
        # Alice (Eng): Promoter, High Scores
        Response(employee_id=employees[0].id, survey_id=survey.id, enps=10, feedback_score=5, learning=5),
        # Bob (Eng): Detractor, Low Scores
        Response(employee_id=employees[1].id, survey_id=survey.id, enps=0, feedback_score=1, learning=1),
        # Charlie (Eng): Passive, Mid Scores
        Response(employee_id=employees[2].id, survey_id=survey.id, enps=8, feedback_score=3, learning=3),
        # Diana (HR): Promoter, Good Scores
        Response(employee_id=employees[3].id, survey_id=survey.id, enps=9, feedback_score=4, learning=4),
    ]
    db_session.add_all(responses)
    db_session.flush()

    # 4. Sentiments (Qualitative)
    # Alice (Eng) - Positive Text
    sent_alice = ResponseSentiment(
        response_id=responses[0].id,
        field_name='learning_comment',
        sentiment_label='POSITIVE',
        sentiment_rating=5,
        sentiment_score=0.9
    )
    # Bob (Eng) - Negative Text
    sent_bob = ResponseSentiment(
        response_id=responses[1].id,
        field_name='learning_comment',
        sentiment_label='NEGATIVE',
        sentiment_rating=1,
        sentiment_score=0.9
    )

    db_session.add_all([sent_alice, sent_bob])
    db_session.commit()

    return {"eng_id": dept_eng.id, "hr_id": dept_hr.id, "emp_alice_id": employees[0].id}


class TestDashboardService:
    """
    Level 2 Tests: Dashboard Business Logic & Math.
    """

    def test_get_overview_data_global(self, db_session, dashboard_data):
        """
        GIVEN the controlled dataset
        WHEN get_overview_data is called without filters
        THEN it should calculate correct Company-wide eNPS and Averages
        """
        data = DashboardService.get_overview_data(dept_id=None, role=None)

        metrics = data['metrics']

        # Total Employees
        assert metrics['total_employees'] == 4

        # Avg Feedback: (5 + 1 + 3 + 4) / 4 = 13 / 4 = 3.25 -> Round to 3.2 or 3.3
        # Service rounds to 1 decimal
        assert metrics['avg_feedback'] == 3.2

        # eNPS: 25.0 (Calculated in fixture docstring)
        assert metrics['enps'] == 25.0

    def test_get_overview_data_filtered_dept(self, db_session, dashboard_data):
        """
        GIVEN the controlled dataset
        WHEN get_overview_data is called with Engineering Dept ID
        THEN it should calculate metrics ONLY for Engineering
        """
        eng_id = dashboard_data['eng_id']
        data = DashboardService.get_overview_data(dept_id=eng_id, role=None)

        metrics = data['metrics']

        # Eng has 3 employees
        assert metrics['total_employees'] == 3

        # Eng eNPS: (1 Promoter - 1 Detractor) / 3 = 0.0
        assert metrics['enps'] == 0.0

        # View Context should update
        assert data['view_context'] == "Engineering"

    def test_get_overview_data_filtered_role(self, db_session, dashboard_data):
        """
        GIVEN the controlled dataset
        WHEN get_overview_data is called with Role='Dev'
        THEN it should only count Alice and Bob
        """
        data = DashboardService.get_overview_data(dept_id=None, role="Dev")

        # Alice (10) + Bob (0).
        # eNPS: 1 Promoter (50%) - 1 Detractor (50%) = 0.0
        assert data['metrics']['enps'] == 0.0
        assert data['metrics']['total_employees'] == 2

    def test_get_company_deep_dive_radars(self, db_session, dashboard_data):
        """
        GIVEN the dataset
        WHEN get_company_deep_dive_data is called
        THEN it should correctly aggregate AI Sentiment and User Scores
        """
        data = DashboardService.get_company_deep_dive_data()

        # Check User Radar (Quantitative)
        # We look at 'Learning' index. Order: Role, Contrib, Learning...
        # Learning Avg: (5+1+3+4)/4 = 3.25 -> 3.2
        user_radar = data['charts']['user_radar']['data']
        # 'Learning' is the 3rd item (index 2) in the list defined in Service
        assert user_radar[2] == 3.2

        # Check AI Radar (Qualitative)
        # We only added Learning comments for Alice (5) and Bob (1).
        # Avg: (5+1)/2 = 3.0
        ai_radar = data['charts']['ai_radar']['data']
        # 'Learning' is index 2
        assert ai_radar[2] == 3.0

    def test_get_area_intelligence_comparison(self, db_session, dashboard_data):
        """
        GIVEN multiple departments
        WHEN get_area_intelligence_data is called
        THEN it should return comparative scores sorted by score
        """
        data = DashboardService.get_area_intelligence_data(dept_id=None, metric_key='feedback')

        # HR Avg Feedback: 4.0 (Diana)
        # Eng Avg Feedback: (5+1+3)/3 = 3.0

        comparison = data['comparison']
        names = comparison['labels']
        values = comparison['user_values']

        # Should be sorted descending by default
        assert names[0] == "HR"
        assert values[0] == 4.0

        assert names[1] == "Engineering"
        assert values[1] == 3.0

    def test_get_employee_profile_data(self, db_session, dashboard_data):
        """
        GIVEN a specific employee ID
        WHEN get_employee_profile_data is called
        THEN it should return their individual scores and the Dept Average benchmark
        """
        alice_id = dashboard_data['emp_alice_id']
        data = DashboardService.get_employee_profile_data(emp_id=alice_id)

        # Check Employee specific data
        assert data['employee']['details'].name == "Alice"

        # Alice's Learning Score is 5.0 (Index 2)
        assert data['employee']['scores'][2] == 5.0

        # Dept Average (Engineering) for Learning
        # (5+1+3)/3 = 3.0
        # The service returns dept_avgs list
        dept_avgs = data['employee']['dept_avgs']
        assert dept_avgs[2] == 3.0

    def test_edge_case_no_data(self, db_session):
        """
        GIVEN an empty database
        WHEN Service methods are called
        THEN they should handle it gracefully (return 0s, not crash)
        """
        # Overview
        overview = DashboardService.get_overview_data(None, None)
        assert overview['metrics']['total_employees'] == 0
        assert overview['metrics']['enps'] == 0.0

        # Deep Dive
        dive = DashboardService.get_company_deep_dive_data()
        assert dive['metrics']['conversion_rate'] == 0

        # Profile
        profile = DashboardService.get_employee_profile_data(999)  # Non-existent ID
        assert profile['employee'] is None