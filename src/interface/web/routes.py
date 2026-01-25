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


@web_bp.route('/areas')
def areas_view():
    """
    Task 7 Refined: Area Level Visualization.
    Features:
    1. Dynamic Comparative Chart: User selects specific metric (e.g., 'Learning') to benchmark across departments.
    2. Deep Dive: Department specific eNPS and Dual Radar analysis.
    """

    # --- Configuration: Metric Mapping Strategy ---
    # Maps URL slug -> (DB Column, AI Field Name, Display Label)
    metrics_config = {
        'role_interest': {
            'col': Response.role_interest,
            'ai_field': 'role_interest_comment',
            'label': 'Role Interest'
        },
        'contribution': {
            'col': Response.contribution,
            'ai_field': 'contribution_comment',
            'label': 'Contribution'
        },
        'learning': {
            'col': Response.learning,
            'ai_field': 'learning_comment',
            'label': 'Learning'
        },
        'feedback': {
            'col': Response.feedback_score,  # Note: column has _score suffix
            'ai_field': 'feedback_comment',
            'label': 'Feedback Culture'
        },
        'manager_interaction': {
            'col': Response.manager_interaction,
            'ai_field': 'manager_interaction_comment',
            'label': 'Manager Bond'
        },
        'career_clarity': {
            'col': Response.career_clarity,
            'ai_field': 'career_clarity_comment',
            'label': 'Career Clarity'
        },
        'permanence': {
            'col': Response.permanence,
            'ai_field': 'permanence_comment',
            'label': 'Retention/Permanence'
        },
        'enps_score': {  # Renamed to avoid confusion with the calculated KPI
            'col': Response.enps,
            'ai_field': 'enps_comment',
            'label': 'eNPS (Score)'
        }
    }

    # 1. Capture Inputs
    selected_dept_id = request.args.get('dept_id', type=int)
    selected_metric_key = request.args.get('metric', 'role_interest')  # Default to Role Interest

    # Validation: Fallback if invalid metric passed
    if selected_metric_key not in metrics_config:
        selected_metric_key = 'role_interest'

    current_metric = metrics_config[selected_metric_key]

    # --- PART A: Comparative Landscape (Dynamic Metric) ---

    # Query 1: User Scores (Avg of Selected Column)
    user_comparison = db.session.query(
        Department.id,
        Department.name,
        func.avg(current_metric['col']).label('avg_score')
    ).join(Employee, Employee.department_id == Department.id) \
        .join(Response, Response.employee_id == Employee.id) \
        .group_by(Department.id, Department.name).all()

    # Query 2: AI Sentiment (Avg of Selected Field)
    ai_comparison = db.session.query(
        Department.id,
        func.avg(ResponseSentiment.sentiment_rating).label('avg_sentiment')
    ).join(Response, ResponseSentiment.response_id == Response.id) \
        .join(Employee, Response.employee_id == Employee.id) \
        .join(Department, Employee.department_id == Department.id) \
        .filter(ResponseSentiment.field_name == current_metric['ai_field']) \
        .group_by(Department.id).all()

    # Merge Data
    comp_data = {}
    for row in user_comparison:
        comp_data[row.id] = {
            'name': row.name,
            'user': round(row.avg_score, 1) if row.avg_score else 0,
            'ai': 0
        }
    for row in ai_comparison:
        if row.id in comp_data:
            comp_data[row.id]['ai'] = round(row.avg_sentiment, 1) if row.avg_sentiment else 0

    # Sort by User Score desc
    sorted_comp = sorted(comp_data.values(), key=lambda x: x['user'], reverse=True)
    comp_labels = [x['name'] for x in sorted_comp]
    comp_user_values = [x['user'] for x in sorted_comp]
    comp_ai_values = [x['ai'] for x in sorted_comp]

    # --- PART B: Deep Dive (Selected Department) ---
    deep_dive_data = None
    selected_dept_name = "Select a Department"
    dept_enps_score = None  # Calculated eNPS %

    if selected_dept_id:
        dept = Department.query.get(selected_dept_id)
        if dept:
            selected_dept_name = dept.name

            # 1. Calculate eNPS for this Department
            # Formula: % Promoters (9-10) - % Detractors (0-6)
            enps_stats = db.session.query(
                func.count(Response.id).label('total'),
                func.sum(case((Response.enps >= 9, 1), else_=0)).label('promoters'),
                func.sum(case((Response.enps <= 6, 1), else_=0)).label('detractors')
            ).join(Employee, Response.employee_id == Employee.id) \
                .filter(Employee.department_id == selected_dept_id).first()

            if enps_stats and enps_stats.total > 0:
                p_pct = (enps_stats.promoters or 0) / enps_stats.total
                d_pct = (enps_stats.detractors or 0) / enps_stats.total
                dept_enps_score = round((p_pct - d_pct) * 100, 1)
            else:
                dept_enps_score = 0

            # 2. Filtered User Scores (Radar)
            user_stats = db.session.query(
                func.avg(Response.role_interest),
                func.avg(Response.contribution),
                func.avg(Response.learning),
                func.avg(Response.feedback_score),
                func.avg(Response.manager_interaction),
                func.avg(Response.career_clarity),
                func.avg(Response.permanence),
                func.avg(Response.enps)
            ).join(Employee, Response.employee_id == Employee.id) \
                .filter(Employee.department_id == selected_dept_id).first()

            # 3. Filtered AI Sentiment (Radar)
            sentiment_stats = db.session.query(
                ResponseSentiment.field_name,
                func.avg(ResponseSentiment.sentiment_rating)
            ).join(Response, ResponseSentiment.response_id == Response.id) \
                .join(Employee, Response.employee_id == Employee.id) \
                .filter(Employee.department_id == selected_dept_id) \
                .group_by(ResponseSentiment.field_name).all()

            # Processing Logic (Mapping DB fields to Radar Order)
            # Reusing the order from config logic implicitly
            radar_labels_order = [
                'Role Interest', 'Contribution', 'Learning', 'Feedback Culture',
                'Manager Bond', 'Career Clarity', 'Retention/Permanence', 'eNPS (Score)'
            ]

            # Helper: construct values list matching the order above
            # AI
            ai_dict = {row[0]: (row[1] or 0) for row in sentiment_stats}
            ai_values = []
            # We iterate through config items to ensure matching order is tricky because dicts are unordered in older pythons
            # Let's use a fixed list of keys corresponding to radar_labels_order
            keys_order = ['role_interest', 'contribution', 'learning', 'feedback', 'manager_interaction',
                          'career_clarity', 'permanence', 'enps_score']

            for key in keys_order:
                conf = metrics_config[key]
                ai_values.append(round(ai_dict.get(conf['ai_field'], 0), 2))

            # User
            user_values = []
            if user_stats:
                def safe(val): return round(val, 1) if val else 0

                user_values = [
                    safe(user_stats[0]), safe(user_stats[1]), safe(user_stats[2]),
                    safe(user_stats[3]), safe(user_stats[4]), safe(user_stats[5]),
                    safe(user_stats[6]), safe(user_stats[7])
                ]

            deep_dive_data = {
                'labels': radar_labels_order,
                'user_data': user_values,
                'ai_data': ai_values,
                'enps': dept_enps_score
            }

    # Departments for Dropdown
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        'areas.html',
        active_page='areas',
        departments=departments,
        metrics_options=metrics_config,  # Pass config to template for dropdown
        selected_metric=selected_metric_key,
        selected_metric_label=current_metric['label'],
        selected_dept_id=selected_dept_id,
        selected_dept_name=selected_dept_name,
        comparison={
            'labels': comp_labels,
            'user_values': comp_user_values,
            'ai_values': comp_ai_values
        },
        deep_dive=deep_dive_data
    )


@web_bp.route('/employees')
def employees_view():
    """
    Task 8 Final: Employee Level Visualization.
    Features:
    1. Search: Datalist for employees.
    2. Benchmark Radar: Fixed logic to ensure Company vs Dept filters apply correctly.
    3. eNPS Focus: Dedicated card for eNPS score + AI Sentiment of that specific comment.
    4. Cleanup: Removed Action Plans and generic sentiment lists.
    """
    # 1. Capture Filter
    selected_emp_id = request.args.get('emp_id', type=int)

    # Helper to calculate averages for the radar chart
    # Refined to ensure the filter is applied correctly
    def calculate_averages(query_filter=None):
        q = db.session.query(
            func.avg(Response.role_interest),
            func.avg(Response.contribution),
            func.avg(Response.learning),
            func.avg(Response.feedback_score),
            func.avg(Response.manager_interaction),
            func.avg(Response.career_clarity),
            func.avg(Response.permanence),
            func.avg(Response.enps)
        ).join(Employee, Response.employee_id == Employee.id)

        # FIX: Explicit check to avoid boolean ambiguity with SQLAlchemy expressions
        if query_filter is not None:
            q = q.filter(query_filter)

        res = q.first()
        # Handle None results (convert to 0.0)
        return [round(x, 1) if x else 0.0 for x in res] if res else [0.0] * 8

    # A. Company Averages (Global Benchmark - No Filter)
    company_avgs = calculate_averages(None)

    # Initialize variables
    dept_avgs = [0.0] * 8
    employee_data = None

    if selected_emp_id:
        emp = Employee.query.get(selected_emp_id)

        if emp:
            # Fetch latest Response
            resp = Response.query.filter_by(employee_id=emp.id).first()

            if resp:
                # 1. Employee Quantitative Scores
                emp_scores = [
                    float(resp.role_interest or 0),
                    float(resp.contribution or 0),
                    float(resp.learning or 0),
                    float(resp.feedback_score or 0),
                    float(resp.manager_interaction or 0),
                    float(resp.career_clarity or 0),
                    float(resp.permanence or 0),
                    float(resp.enps or 0)
                ]

                # 2. Dept Averages (Local Benchmark - Filter by Dept ID)
                dept_avgs = calculate_averages(Employee.department_id == emp.department_id)

                # 3. eNPS Specific Sentiment Analysis (The "Voice")
                # We specifically look for the sentiment associated with the 'enps_comment' field
                enps_sentiment_data = None

                # Try to fetch sentiment from DB if AI ran
                sentiment_record = db.session.query(ResponseSentiment).filter_by(
                    response_id=resp.id,
                    field_name='enps_comment'
                ).first()

                if sentiment_record:
                    enps_sentiment_data = {
                        'label': sentiment_record.sentiment_label,  # POSITIVE/NEGATIVE/NEUTRAL
                        'score': sentiment_record.sentiment_score,  # Confidence score
                        'rating': sentiment_record.sentiment_rating  # 1-5 Scale
                    }

                employee_data = {
                    'details': emp,
                    'scores': emp_scores,
                    'dept_avgs': dept_avgs,
                    'enps_comment': resp.enps_comment,
                    'enps_sentiment': enps_sentiment_data
                }

    # Search List (Optimized)
    all_employees = db.session.query(
        Employee.id, Employee.name, Employee.email, Employee.corporate_email
    ).order_by(Employee.name).all()

    # Radar Labels
    radar_labels = [
        'Role Interest', 'Contribution', 'Learning', 'Feedback',
        'Manager Bond', 'Career Path', 'Retention', 'eNPS'
    ]

    return render_template(
        'employees.html',
        active_page='employees',
        search_list=all_employees,
        selected_emp_id=selected_emp_id,
        employee=employee_data,
        chart_config={
            'labels': radar_labels,
            'company_data': company_avgs
        }
    )