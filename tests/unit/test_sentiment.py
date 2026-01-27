import pytest
from unittest.mock import patch, MagicMock
from src.application.services.sentiment import SentimentAnalysisService
from src.domain.models import Response, ResponseSentiment


class TestSentimentService:
    """
    Level 1 Tests: Core AI Logic.
    Focuses on the SentimentAnalysisService robustness and atomic operations.
    """

    def test_map_stars_to_label(self):
        """
        GIVEN a specific star rating string from the model
        WHEN _map_stars_to_label is called
        THEN it should return the correct business domain label
        """
        # Valid cases
        assert SentimentAnalysisService._map_stars_to_label("5 stars") == "POSITIVE"
        assert SentimentAnalysisService._map_stars_to_label("4 stars") == "POSITIVE"
        assert SentimentAnalysisService._map_stars_to_label("3 stars") == "NEUTRAL"
        assert SentimentAnalysisService._map_stars_to_label("2 stars") == "NEGATIVE"
        assert SentimentAnalysisService._map_stars_to_label("1 star") == "NEGATIVE"

        # Edge cases (Model weirdness)
        assert SentimentAnalysisService._map_stars_to_label("invalid") == "NEUTRAL"

    @patch('src.application.services.sentiment.SentimentAnalysisService.get_pipeline')
    def test_analyze_response_creation(self, mock_get_pipeline, db_session, sample_data):
        """
        GIVEN a response with a valid comment
        WHEN analyze_response is called
        THEN a new ResponseSentiment record should be created in the DB
        """
        # 1. Arrange: Setup Data and Mock
        # Mock the HuggingFace pipeline callable
        mock_analyzer = MagicMock()
        mock_analyzer.return_value = [{'label': '5 stars', 'score': 0.99}]
        mock_get_pipeline.return_value = mock_analyzer

        # Create a response with text
        emp = sample_data['emp']
        survey = sample_data['survey']
        response = Response(
            employee_id=emp.id,
            survey_id=survey.id,
            role_interest_comment="I love this job, it is amazing!"
        )
        db_session.add(response)
        db_session.commit()

        # 2. Act
        SentimentAnalysisService.analyze_response(response.id)

        # 3. Assert
        sentiment = ResponseSentiment.query.filter_by(
            response_id=response.id,
            field_name='role_interest_comment'
        ).first()

        assert sentiment is not None
        assert sentiment.sentiment_label == "POSITIVE"
        assert sentiment.sentiment_rating == 5
        assert sentiment.sentiment_score == 0.99

    @patch('src.application.services.sentiment.SentimentAnalysisService.get_pipeline')
    def test_analyze_response_upsert(self, mock_get_pipeline, db_session, sample_data):
        """
        GIVEN a response that already has a sentiment analysis
        WHEN analyze_response is called again (e.g., re-run)
        THEN it should update the existing record, not duplicate it
        """
        # 1. Arrange
        mock_analyzer = MagicMock()
        mock_analyzer.return_value = [{'label': '1 star', 'score': 0.88}]  # Changed to Negative
        mock_get_pipeline.return_value = mock_analyzer

        # Create response
        emp = sample_data['emp']
        survey = sample_data['survey']
        response = Response(employee_id=emp.id, survey_id=survey.id, enps_comment="Bad.")
        db_session.add(response)
        db_session.commit()

        # Create PRE-EXISTING sentiment
        old_sentiment = ResponseSentiment(
            response_id=response.id,
            field_name='enps_comment',
            sentiment_label='POSITIVE',  # Old wrong value
            sentiment_score=0.5,
            sentiment_rating=5
        )
        db_session.add(old_sentiment)
        db_session.commit()

        # 2. Act
        SentimentAnalysisService.analyze_response(response.id)

        # 3. Assert
        count = ResponseSentiment.query.filter_by(response_id=response.id).count()
        assert count == 1  # Still one record

        updated = ResponseSentiment.query.filter_by(response_id=response.id).first()
        assert updated.sentiment_label == "NEGATIVE"  # Value updated
        assert updated.sentiment_rating == 1

    @patch('src.application.services.sentiment.SentimentAnalysisService.get_pipeline')
    def test_analyze_skip_short_text(self, mock_get_pipeline, db_session, sample_data):
        """
        GIVEN a response with very short/empty text
        WHEN analyze_response is called
        THEN it should NOT call the AI model and NOT save sentiment
        """
        # 1. Arrange
        mock_analyzer = MagicMock()
        mock_get_pipeline.return_value = mock_analyzer

        emp = sample_data['emp']
        survey = sample_data['survey']
        response = Response(
            employee_id=emp.id,
            survey_id=survey.id,
            feedback_comment="-"  # Too short
        )
        db_session.add(response)
        db_session.commit()

        # 2. Act
        SentimentAnalysisService.analyze_response(response.id)

        # 3. Assert
        # Ensure model was NOT called
        mock_analyzer.assert_not_called()

        # Ensure DB is empty
        count = ResponseSentiment.query.filter_by(response_id=response.id).count()
        assert count == 0