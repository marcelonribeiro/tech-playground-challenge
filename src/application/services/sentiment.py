import logging
from transformers import pipeline
from sqlalchemy.exc import SQLAlchemyError
from src.extensions import db
from src.domain.models import Response, ResponseSentiment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SentimentAnalysisService:
    """
    Core AI Service using HuggingFace Transformers.
    Analyzes comments in Portuguese and stores granular sentiment data
    in the ResponseSentiment table.
    """

    # Model: Multilingual BERT fine-tuned for sentiment analysis.
    # Output: '1 star' to '5 stars'.
    MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"

    _pipeline = None

    @classmethod
    def get_pipeline(cls):
        """
        Singleton pattern for loading the AI model.
        Loading a Transformer model is memory-expensive, so we do it only once.
        """
        if cls._pipeline is None:
            logger.info(f"AI: Loading model {cls.MODEL_NAME} into memory...")
            try:
                cls._pipeline = pipeline(
                    "sentiment-analysis",
                    model=cls.MODEL_NAME,
                    tokenizer=cls.MODEL_NAME,
                    truncation=True,
                    max_length=512
                )
                logger.info("AI: Model loaded successfully.")
            except Exception as e:
                logger.critical(f"AI: Failed to load model. Error: {e}")
                raise e
        return cls._pipeline

    @staticmethod
    def _map_stars_to_label(star_label: str) -> str:
        """
        Maps the model output ('N stars') to our business domain labels.
        """
        # Format usually comes as '5 stars' or '1 star'
        try:
            stars = int(star_label.split()[0])
            if stars >= 4:
                return "POSITIVE"
            elif stars <= 2:
                return "NEGATIVE"
            else:
                return "NEUTRAL"
        except (ValueError, IndexError):
            logger.warning(f"AI: Could not parse label '{star_label}', defaulting to NEUTRAL")
            return "NEUTRAL"

    @classmethod
    def analyze_response(cls, response_id: int):
        """
        Analyzes all text fields of a specific response entity.
        Performs upsert (update if exists, insert if new) to ensure idempotency.
        """
        response = db.session.get(Response, response_id)
        if not response:
            logger.error(f"AI: Response ID {response_id} not found.")
            return

        # Define which fields contain text to be analyzed
        comment_fields = [
            'role_interest_comment',
            'contribution_comment',
            'learning_comment',
            'feedback_comment',
            'manager_interaction_comment',
            'career_clarity_comment',
            'permanence_comment',
            'enps_comment'
        ]

        analyzer = cls.get_pipeline()

        # Track changes to avoid empty commits
        changes_count = 0

        for field_name in comment_fields:
            text_content = getattr(response, field_name)

            # Skip empty comments or very short placeholders (e.g. "-", ".")
            if not text_content or len(str(text_content).strip()) < 3:
                continue

            try:
                # Run Inference
                # Result format: [{'label': '5 stars', 'score': 0.98}]
                result = analyzer(str(text_content))[0]
                stars_int = int(result['label'].split()[0])

                label = cls._map_stars_to_label(result['label'])
                score = float(result['score'])

                # Upsert Logic: Check if sentiment already exists for this field
                existing_sentiment = ResponseSentiment.query.filter_by(
                    response_id=response.id,
                    field_name=field_name
                ).first()

                if existing_sentiment:
                    # Update existing record
                    existing_sentiment.sentiment_label = label
                    existing_sentiment.sentiment_score = score
                    existing_sentiment.sentiment_rating = stars_int
                else:
                    # Create new record
                    new_sentiment = ResponseSentiment(
                        response_id=response.id,
                        field_name=field_name,
                        sentiment_label=label,
                        sentiment_score=score,
                        sentiment_rating=stars_int
                    )
                    db.session.add(new_sentiment)

                changes_count += 1

            except Exception as e:
                logger.error(f"AI: Error processing field '{field_name}' for Response {response.id}: {e}")
                continue

        if changes_count > 0:
            db.session.flush()
            logger.info(f"AI: Analyzed Response {response_id}. Staged {changes_count} sentiments.")
