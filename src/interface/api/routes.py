from flask import Blueprint, request, jsonify, current_app
from src.domain.models import Employee, Department
from src.domain.schemas import PaginatedEmployeeResponse, EmployeeResponse, DashboardStats, SentimentOverviewResponse
from src.application.services.analytics import AnalyticsService
from src.extensions import db

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

@api_bp.route('/employees', methods=['GET'])
def list_employees():
    """
    Get paginated list of employees.
    Supports filtering by department_id.
    Task 9 Bonus: Pagination + Filtering.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    department_id = request.args.get('department_id', type=int)
    role = request.args.get('role', type=str)

    query = Employee.query

    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if role:
        query = query.filter(Employee.role.ilike(f"%{role}%"))

    # Pagination provided by Flask-SQLAlchemy
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Serialization with Pydantic
    response_data = PaginatedEmployeeResponse(
        items=[EmployeeResponse.model_validate(e) for e in pagination.items],
        total=pagination.total,
        page=pagination.page,
        per_page=pagination.per_page,
        pages=pagination.pages
    )

    return jsonify(response_data.model_dump())


@api_bp.route('/dashboard/company', methods=['GET'])
def get_company_metrics():
    """
    Returns high-level company metrics for the dashboard.
    """
    enps_data = AnalyticsService.calculate_enps()

    total_employees = Employee.query.count()

    if total_employees > 0:
        participation = (enps_data.total_responses / total_employees) * 100
    else:
        participation = 0

    stats = DashboardStats(
        company_enps=enps_data,
        total_employees=total_employees,
        participation_rate=round(participation, 1)
    )

    return jsonify(stats.model_dump())


@api_bp.route('/departments', methods=['GET'])
def list_departments():
    """Helper endpoint for frontend dropdowns."""
    depts = Department.query.order_by(Department.name).all()
    return jsonify([{"id": d.id, "name": d.name} for d in depts])


@api_bp.route('/analytics/sentiment-overview', methods=['GET'])
def get_sentiment_overview():
    """
    Returns aggregated AI sentiment metrics.
    Useful for heatmaps and identifying cultural pain points.
    """
    department_id = request.args.get('department_id', type=int)

    try:
        raw_metrics = AnalyticsService.get_sentiment_overview(department_id)

        response = SentimentOverviewResponse(
            department_id=department_id,
            metrics=raw_metrics
        )

        return jsonify(response.model_dump())

    except Exception as e:
        current_app.logger.error(f"Error fetching sentiment overview: {e}")
        return jsonify({"error": "Failed to calculate sentiment metrics"}), 500