from flask import render_template, request
from sqlalchemy import func, case
from src.extensions import db
from src.domain.models import Department, Response, Employee, ResponseSentiment
from . import web_bp


@web_bp.route('/')
def index():
    """
    Task 2 Refined: Executive Dashboard.
    Renders high-level metrics with robust filtering (Department + Role).
    """
    # 1. Capture Filter Parameters
    dept_id_arg = request.args.get('dept_id', type=int)
    role_arg = request.args.get('role', type=str)

    # 2. Base Queries (Join Response -> Employee for filtering)
    resp_query = db.session.query(Response).join(Employee, Response.employee_id == Employee.id)
    emp_query = db.session.query(Employee)

    # 3. Apply Filters
    # Context label to show user what they are looking at (e.g., "Engineering - Senior Dev")
    view_context = "Company Level"

    if dept_id_arg:
        resp_query = resp_query.filter(Employee.department_id == dept_id_arg)
        emp_query = emp_query.filter(Employee.department_id == dept_id_arg)
        # Get Department Name for display
        dept_name = Department.query.get(dept_id_arg).name
        view_context = dept_name

    if role_arg:
        resp_query = resp_query.filter(Employee.role == role_arg)
        emp_query = emp_query.filter(Employee.role == role_arg)
        # Append role to context
        if dept_id_arg:
            view_context += f" ({role_arg})"
        else:
            view_context = f"Role: {role_arg}"

    # 4. Calculate Key Metrics (Filtered)
    total_employees = emp_query.count()

    # Average Feedback
    avg_feedback = resp_query.with_entities(func.avg(Response.feedback_score)).scalar()
    avg_feedback = round(avg_feedback, 1) if avg_feedback else 0.0

    # eNPS Calculation
    enps_stats = resp_query.with_entities(
        func.count(Response.id).label('total'),
        func.sum(case((Response.enps >= 9, 1), else_=0)).label('promoters'),
        func.sum(case((Response.enps <= 6, 1), else_=0)).label('detractors')
    ).first()

    enps_score = 0
    if enps_stats and enps_stats.total > 0:
        promoters_pct = (enps_stats.promoters or 0) / enps_stats.total
        detractors_pct = (enps_stats.detractors or 0) / enps_stats.total
        enps_score = (promoters_pct - detractors_pct) * 100

    # 5. Chart Data: Employees per Department (Always Global context is better for comparison)
    dept_counts = db.session.query(
        Department.name,
        func.count(Employee.id)
    ).join(Employee, Employee.department_id == Department.id) \
        .group_by(Department.name).all()

    chart_labels = [d[0] for d in dept_counts]
    chart_values = [d[1] for d in dept_counts]

    # 6. Fetch Dropdown Options
    departments = Department.query.order_by(Department.name).all()
    # Fetch distinct roles for the dropdown
    roles = db.session.query(Employee.role).distinct().order_by(Employee.role).all()
    roles_list = [r[0] for r in roles if r[0]]  # Flatten list of tuples

    return render_template(
        'dashboard.html',
        active_page='overview',
        departments=departments,
        roles=roles_list,
        selected_dept_id=dept_id_arg,
        selected_role=role_arg,
        view_context=view_context,
        metrics={
            'total_employees': total_employees,
            'avg_feedback': avg_feedback,
            'enps': round(enps_score, 1)
        },
        chart_data={
            'labels': chart_labels,
            'data': chart_values
        }
    )


@web_bp.route('/company')
def company_view():
    """
    Task 6: Company Level Visualization (Refined).
    Focus:
    1. Conversion Rate (Snapshot).
    2. Tenure Distribution (Ordered by Rank).
    3. Dual Radar Analysis: AI Sentiment (Qualitative) vs User Scores (Quantitative).
    """

    # --- 1. KPI: Survey Conversion Rate ---
    total_employees = db.session.query(func.count(Employee.id)).scalar() or 0
    total_responses = db.session.query(func.count(Response.id)).scalar() or 0

    conversion_rate = 0
    if total_employees > 0:
        conversion_rate = (total_responses / total_employees) * 100

    # --- 2. Tenure Distribution (Ordered by Rank) ---
    tenure_groups = db.session.query(
        Employee.tenure,
        func.count(Employee.id)
    ).group_by(
        Employee.tenure,
        Employee.tenure_rank
    ).order_by(Employee.tenure_rank).all()

    tenure_labels = [t[0] or "Unknown" for t in tenure_groups]
    tenure_values = [t[1] for t in tenure_groups]

    # --- 3. Dual Radar Analysis Setup ---

    # Map for AI Data (ResponseSentiment table)
    # This remains the same as sentiment fields are consistent
    ai_field_mapping = {
        'role_interest_comment': 'Role Interest',
        'contribution_comment': 'Contribution',
        'learning_comment': 'Learning',
        'feedback_comment': 'Feedback',
        'manager_interaction_comment': 'Manager Bond',
        'career_clarity_comment': 'Career Path',
        'permanence_comment': 'Retention',
        'enps_comment': 'eNPS Reason'
    }

    # --- A. AI Sentiment Radar (Qualitative 1-5) ---
    sentiment_stats = db.session.query(
        ResponseSentiment.field_name,
        func.avg(ResponseSentiment.sentiment_rating)
    ).group_by(ResponseSentiment.field_name).all()

    ai_radar_labels = []
    ai_radar_values = []

    # Convert to dict for O(1) lookup
    ai_data_dict = {row[0]: (row[1] or 0) for row in sentiment_stats}

    # Order based on the defined mapping
    for db_field, label in ai_field_mapping.items():
        score = ai_data_dict.get(db_field, 0)
        ai_radar_labels.append(label)
        ai_radar_values.append(round(score, 2))


    # --- B. User Score Radar (Quantitative 0-10) ---
    # FIX: Corrected column names based on models.py
    # Note: 'feedback_score' has _score, others do not.
    user_stats_query = db.session.query(
        func.avg(Response.role_interest),  # Corrected
        func.avg(Response.contribution),  # Corrected
        func.avg(Response.learning),  # Corrected
        func.avg(Response.feedback_score),  # This one actually has _score
        func.avg(Response.manager_interaction),  # Corrected
        func.avg(Response.career_clarity),  # Corrected
        func.avg(Response.permanence),  # Corrected
        func.avg(Response.enps)  # Corrected
    ).first()

    user_radar_values = []

    if user_stats_query:
        # Helper to safely round
        def safe_round(val): return round(val, 1) if val is not None else 0


        # Must match the order of 'ai_field_mapping' logic above:
        # Role, Contribution, Learning, Feedback, Manager, Career, Retention, eNPS
        user_radar_values = [
            safe_round(user_stats_query[0]),  # Role Interest
            safe_round(user_stats_query[1]),  # Contribution
            safe_round(user_stats_query[2]),  # Learning
            safe_round(user_stats_query[3]),  # Feedback Score
            safe_round(user_stats_query[4]),  # Manager Interaction
            safe_round(user_stats_query[5]),  # Career Clarity
            safe_round(user_stats_query[6]),  # Permanence
            safe_round(user_stats_query[7])  # eNPS
        ]

    return render_template(
        'company.html',
        active_page='company',
        metrics={
            'conversion_rate': round(conversion_rate, 1),
            'total_responses': total_responses,
            'total_invited': total_employees
        },
        charts={
            'tenure': {'labels': tenure_labels, 'data': tenure_values},
            'ai_radar': {'labels': ai_radar_labels, 'data': ai_radar_values},
            'user_radar': {'labels': ai_radar_labels, 'data': user_radar_values}
        }
    )