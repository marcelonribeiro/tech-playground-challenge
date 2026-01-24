from src.application.services.analytics import AnalyticsService
from src.domain.models import Response


def test_calculate_enps_empty(db_session):
    """
    GIVEN no responses in the database
    WHEN calculate_enps is called
    THEN it should return 0 score and 'Insufficient Data'
    """
    metrics = AnalyticsService.calculate_enps()
    assert metrics.total_responses == 0
    assert metrics.classification == "Insufficient Data"


def test_calculate_enps_scenario(db_session, sample_data):
    """
    GIVEN a mix of Promoters (9-10), Passives (7-8) and Detractors (0-6)
    WHEN calculate_enps is called
    THEN the score should be calculated correctly: %Promoters - %Detractors
    """
    emp_id = sample_data['emp'].id
    survey_id = sample_data['survey'].id

    # Scenario:
    # 1 Promoter (10)
    # 1 Passive (8)
    # 2 Detractors (5, 0)
    # Total = 4.
    # Promoters% = 25%. Detractors% = 50%.
    # eNPS = 25 - 50 = -25.

    responses = [
        Response(employee_id=emp_id, survey_id=survey_id, enps=10),
        Response(employee_id=emp_id, survey_id=survey_id, enps=8),
        Response(employee_id=emp_id, survey_id=survey_id, enps=5),
        Response(employee_id=emp_id, survey_id=survey_id, enps=0),
    ]
    db_session.add_all(responses)
    db_session.commit()

    metrics = AnalyticsService.calculate_enps()

    assert metrics.total_responses == 4
    assert metrics.promoters_pct == 25.0
    assert metrics.detractors_pct == 50.0
    assert metrics.score == -25
    assert metrics.classification == "Needs Improvement"