from sqlalchemy import func, case
from src.extensions import db
from src.domain.models import Response, Employee, ResponseSentiment
from src.domain.schemas import ENPSMetric


class AnalyticsService:
    """
    Service dedicated to calculating people analytics metrics (eNPS, Engagement, etc).
    """

    @staticmethod
    def calculate_enps(filters=None) -> ENPSMetric:
        """
        Calculates eNPS based on the standard formula:
        eNPS = % Promoters (9-10) - % Detractors (0-6)
        """
        query = db.session.query(
            func.count(Response.id).label('total'),
            func.sum(case((Response.enps >= 9, 1), else_=0)).label('promoters'),
            func.sum(case((Response.enps <= 6, 1), else_=0)).label('detractors')
        )

        # Apply filters (e.g., specific department)
        if filters:
            query = query.join(Employee)
            for key, value in filters.items():
                query = query.filter(getattr(Employee, key) == value)

        result = query.first()

        total = result.total or 0
        if total == 0:
            return ENPSMetric(
                score=0, classification="Insufficient Data",
                promoters_pct=0, detractors_pct=0, passives_pct=0, total_responses=0
            )

        promoters = result.promoters or 0
        detractors = result.detractors or 0
        passives = total - (promoters + detractors)

        promoters_pct = (promoters / total) * 100
        detractors_pct = (detractors / total) * 100
        passives_pct = (passives / total) * 100

        enps_score = int(promoters_pct - detractors_pct)

        # Basic Classification
        if enps_score >= 75:
            classification = "Excellent"
        elif enps_score >= 50:
            classification = "Great"
        elif enps_score >= 0:
            classification = "Good"
        else:
            classification = "Needs Improvement"

        return ENPSMetric(
            score=enps_score,
            classification=classification,
            promoters_pct=round(promoters_pct, 1),
            detractors_pct=round(detractors_pct, 1),
            passives_pct=round(passives_pct, 1),
            total_responses=total
        )


    @staticmethod
    def get_sentiment_overview(department_id: int = None) -> list:
        """
        Aggregates sentiment analysis data by field name.
        Calculates average rating and label distribution.
        """
        # Base query joining Sentiment -> Response -> Employee
        query = db.session.query(
            ResponseSentiment.field_name,
            func.avg(ResponseSentiment.sentiment_rating).label('avg_rating'),
            func.count(ResponseSentiment.id).label('total_count'),
            func.sum(case((ResponseSentiment.sentiment_label == 'POSITIVE', 1), else_=0)).label('pos_count'),
            func.sum(case((ResponseSentiment.sentiment_label == 'NEUTRAL', 1), else_=0)).label('neu_count'),
            func.sum(case((ResponseSentiment.sentiment_label == 'NEGATIVE', 1), else_=0)).label('neg_count')
        ).join(Response, ResponseSentiment.response_id == Response.id) \
            .join(Employee, Response.employee_id == Employee.id)

        # Apply Filter
        if department_id:
            query = query.filter(Employee.department_id == department_id)

        # Group by the comment category
        results = query.group_by(ResponseSentiment.field_name).all()

        # Mapping raw DB fields to clean API labels
        label_map = {
            'role_interest_comment': 'Role Interest',
            'contribution_comment': 'Contribution',
            'learning_comment': 'Learning',
            'feedback_comment': 'Feedback Culture',
            'manager_interaction_comment': 'Manager Bond',
            'career_clarity_comment': 'Career Path',
            'permanence_comment': 'Retention',
            'enps_comment': 'eNPS Context'
        }

        metrics = []
        for row in results:
            # Skip fields not in our map (safety check)
            if row.field_name not in label_map:
                continue

            metrics.append({
                "field_name": row.field_name,
                "friendly_label": label_map.get(row.field_name, row.field_name),
                "average_rating": round(float(row.avg_rating or 0), 2),
                "sample_size": row.total_count,
                "distribution": {
                    "POSITIVE": row.pos_count or 0,
                    "NEUTRAL": row.neu_count or 0,
                    "NEGATIVE": row.neg_count or 0
                }
            })

        # Sort by lowest rating (pain points first)
        metrics.sort(key=lambda x: x['average_rating'])

        return metrics