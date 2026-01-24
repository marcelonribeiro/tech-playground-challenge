from sqlalchemy import func, case
from src.extensions import db
from src.domain.models import Response, Employee, Survey
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
            # Join required if filtering by Employee attributes
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