from typing import Optional, Dict, Any, List
from sqlalchemy import func, case
from src.extensions import db
from src.domain.models import Department, Response, Employee, ResponseSentiment


class DashboardService:
    """
    Application Service responsible for aggregating data, calculating KPIs,
    and preparing structured data for the Web Dashboard Views.
    """

    # Configuration for Area Metrics (Shared constant)
    METRICS_CONFIG = {
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
            'col': Response.feedback_score,
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
        'enps_score': {
            'col': Response.enps,
            'ai_field': 'enps_comment',
            'label': 'eNPS (Score)'
        }
    }

    @staticmethod
    def get_overview_data(dept_id: Optional[int], role: Optional[str]) -> Dict[str, Any]:
        """
        Prepares data for the Executive Dashboard (Overview).
        Handles filtering, KPI calculation, and Chart generation.
        """
        resp_query = db.session.query(Response).join(Employee, Response.employee_id == Employee.id)
        emp_query = db.session.query(Employee)
        view_context = "Company Level"

        # Apply Filters
        if dept_id:
            resp_query = resp_query.filter(Employee.department_id == dept_id)
            emp_query = emp_query.filter(Employee.department_id == dept_id)
            department = db.session.get(Department, dept_id)
            view_context = department.name if department else "Unknown Dept"

        if role:
            resp_query = resp_query.filter(Employee.role == role)
            emp_query = emp_query.filter(Employee.role == role)
            if dept_id:
                view_context += f" ({role})"
            else:
                view_context = f"Role: {role}"

        # Calculate Metrics
        total_employees = emp_query.count()

        avg_feedback = resp_query.with_entities(func.avg(Response.feedback_score)).scalar()
        avg_feedback = round(avg_feedback, 1) if avg_feedback else 0.0

        enps_score = DashboardService._calculate_enps_score(resp_query)

        # Chart Data: Employees per Department
        dept_counts = db.session.query(
            Department.name,
            func.count(Employee.id)
        ).join(Employee, Employee.department_id == Department.id) \
            .group_by(Department.name).all()

        chart_labels = [row[0] for row in dept_counts]
        chart_values = [row[1] for row in dept_counts]

        # Dropdown Options
        departments = Department.query.order_by(Department.name).all()
        roles_raw = db.session.query(Employee.role).distinct().order_by(Employee.role).all()
        roles_list = [r[0] for r in roles_raw if r[0]]

        return {
            'departments': departments,
            'roles': roles_list,
            'view_context': view_context,
            'metrics': {
                'total_employees': total_employees,
                'avg_feedback': avg_feedback,
                'enps': round(enps_score, 1)
            },
            'chart_data': {
                'labels': chart_labels,
                'data': chart_values
            }
        }

    @staticmethod
    def get_company_deep_dive_data() -> Dict[str, Any]:
        """
        Prepares data for Company Level Visualization.
        Includes Conversion Rate, Tenure, and Dual Radar Analysis.
        """
        # KPI: Conversion Rate
        total_employees = db.session.query(func.count(Employee.id)).scalar() or 0
        total_responses = db.session.query(func.count(Response.id)).scalar() or 0
        conversion_rate = (total_responses / total_employees * 100) if total_employees > 0 else 0

        # Tenure Distribution
        tenure_groups = db.session.query(
            Employee.tenure,
            func.count(Employee.id)
        ).group_by(Employee.tenure, Employee.tenure_rank) \
            .order_by(Employee.tenure_rank).all()

        tenure_labels = [t[0] or "Unknown" for t in tenure_groups]
        tenure_values = [t[1] for t in tenure_groups]

        # Radar Analysis
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

        # AI Radar (Qualitative)
        sentiment_stats = db.session.query(
            ResponseSentiment.field_name,
            func.avg(ResponseSentiment.sentiment_rating)
        ).group_by(ResponseSentiment.field_name).all()

        ai_data_dict = {row[0]: (row[1] or 0) for row in sentiment_stats}
        radar_labels = []
        ai_radar_values = []

        for db_field, label in ai_field_mapping.items():
            score = ai_data_dict.get(db_field, 0)
            radar_labels.append(label)
            ai_radar_values.append(round(score, 2))

        # User Score Radar (Quantitative)
        user_stats = db.session.query(
            func.avg(Response.role_interest),
            func.avg(Response.contribution),
            func.avg(Response.learning),
            func.avg(Response.feedback_score),
            func.avg(Response.manager_interaction),
            func.avg(Response.career_clarity),
            func.avg(Response.permanence),
            func.avg(Response.enps)
        ).first()

        user_radar_values = []
        if user_stats:
            def safe_round(val): return round(val, 1) if val is not None else 0

            user_radar_values = [safe_round(val) for val in user_stats]

        return {
            'metrics': {
                'conversion_rate': round(conversion_rate, 1),
                'total_responses': total_responses,
                'total_invited': total_employees
            },
            'charts': {
                'tenure': {'labels': tenure_labels, 'data': tenure_values},
                'ai_radar': {'labels': radar_labels, 'data': ai_radar_values},
                'user_radar': {'labels': radar_labels, 'data': user_radar_values}
            }
        }

    @staticmethod
    def get_area_intelligence_data(dept_id: Optional[int], metric_key: str) -> Dict[str, Any]:
        """
        Prepares data for Department Level Visualization.
        Includes Comparative Bar Chart and specific Department Deep Dive.
        """
        # Validate Metric
        if metric_key not in DashboardService.METRICS_CONFIG:
            metric_key = 'role_interest'

        current_metric = DashboardService.METRICS_CONFIG[metric_key]

        # Comparative Landscape (User Scores)
        user_comparison = db.session.query(
            Department.id,
            Department.name,
            func.avg(current_metric['col']).label('avg_score')
        ).join(Employee, Employee.department_id == Department.id) \
            .join(Response, Response.employee_id == Employee.id) \
            .group_by(Department.id, Department.name).all()

        # Comparative Landscape (AI Sentiment)
        ai_comparison = db.session.query(
            Department.id,
            func.avg(ResponseSentiment.sentiment_rating).label('avg_sentiment')
        ).join(Response, ResponseSentiment.response_id == Response.id) \
            .join(Employee, Response.employee_id == Employee.id) \
            .join(Department, Employee.department_id == Department.id) \
            .filter(ResponseSentiment.field_name == current_metric['ai_field']) \
            .group_by(Department.id).all()

        # Merge & Sort Data
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

        sorted_comp = sorted(comp_data.values(), key=lambda x: x['user'], reverse=True)

        # Deep Dive Logic
        deep_dive_data = None
        selected_dept_name = "Select a Department"

        if dept_id:
            department = db.session.get(Department, dept_id)
            if department:
                selected_dept_name = department.name

                # Department eNPS
                dept_resp_query = db.session.query(Response) \
                    .join(Employee, Response.employee_id == Employee.id) \
                    .filter(Employee.department_id == dept_id)
                dept_enps = DashboardService._calculate_enps_score(dept_resp_query)

                # Department Radars
                deep_dive_data = DashboardService._get_department_radars(dept_id)
                deep_dive_data['enps'] = round(dept_enps, 1)

        departments = Department.query.order_by(Department.name).all()

        return {
            'departments': departments,
            'metrics_options': DashboardService.METRICS_CONFIG,
            'selected_metric_label': current_metric['label'],
            'selected_dept_name': selected_dept_name,
            'comparison': {
                'labels': [x['name'] for x in sorted_comp],
                'user_values': [x['user'] for x in sorted_comp],
                'ai_values': [x['ai'] for x in sorted_comp]
            },
            'deep_dive': deep_dive_data
        }

    @staticmethod
    def get_employee_profile_data(emp_id: Optional[int]) -> Dict[str, Any]:
        """
        Prepares data for Employee Individual Profile.
        Includes Benchmarks (Company/Dept) and specific eNPS Sentiment.
        """
        company_avgs = DashboardService._calculate_radar_averages(None)

        employee_data = None

        if emp_id:
            employee = db.session.get(Employee, emp_id)
            if employee:
                response = Response.query.filter_by(employee_id=employee.id).first()
                if response:
                    emp_scores = [
                        float(response.role_interest or 0),
                        float(response.contribution or 0),
                        float(response.learning or 0),
                        float(response.feedback_score or 0),
                        float(response.manager_interaction or 0),
                        float(response.career_clarity or 0),
                        float(response.permanence or 0),
                        float(response.enps or 0)
                    ]

                    dept_avgs = DashboardService._calculate_radar_averages(
                        Employee.department_id == employee.department_id
                    )

                    enps_sentiment = None
                    sentiment_record = db.session.query(ResponseSentiment).filter_by(
                        response_id=response.id,
                        field_name='enps_comment'
                    ).first()

                    if sentiment_record:
                        enps_sentiment = {
                            'label': sentiment_record.sentiment_label,
                            'score': sentiment_record.sentiment_score,
                            'rating': sentiment_record.sentiment_rating
                        }

                    employee_data = {
                        'details': employee,
                        'scores': emp_scores,
                        'dept_avgs': dept_avgs,
                        'enps_comment': response.enps_comment,
                        'enps_sentiment': enps_sentiment
                    }

        all_employees = db.session.query(
            Employee.id, Employee.name, Employee.email, Employee.corporate_email
        ).order_by(Employee.name).all()

        radar_labels = [
            'Role Interest', 'Contribution', 'Learning', 'Feedback',
            'Manager Bond', 'Career Path', 'Retention', 'eNPS'
        ]

        return {
            'search_list': all_employees,
            'employee': employee_data,
            'chart_config': {
                'labels': radar_labels,
                'company_data': company_avgs
            }
        }

    # Private Helpers

    @staticmethod
    def _calculate_enps_score(query) -> float:
        """Helper to calculate eNPS from a SQLAlchemy Query object."""
        stats = query.with_entities(
            func.count(Response.id).label('total'),
            func.sum(case((Response.enps >= 9, 1), else_=0)).label('promoters'),
            func.sum(case((Response.enps <= 6, 1), else_=0)).label('detractors')
        ).first()

        if stats and stats.total > 0:
            promoters_pct = (stats.promoters or 0) / stats.total
            detractors_pct = (stats.detractors or 0) / stats.total
            return (promoters_pct - detractors_pct) * 100
        return 0.0

    @staticmethod
    def _calculate_radar_averages(query_filter) -> List[float]:
        """Helper to calculate average scores for the 8 key metrics."""
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

        if query_filter is not None:
            q = q.filter(query_filter)

        res = q.first()
        return [round(x, 1) if x else 0.0 for x in res] if res else [0.0] * 8

    @staticmethod
    def _get_department_radars(dept_id: int) -> Dict[str, Any]:
        """Helper to get User and AI radar data for a specific department."""
        # User Scores
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
            .filter(Employee.department_id == dept_id).first()

        def safe(val): return round(val, 1) if val else 0

        user_values = [safe(v) for v in user_stats] if user_stats else [0] * 8

        # AI Sentiment
        sentiment_stats = db.session.query(
            ResponseSentiment.field_name,
            func.avg(ResponseSentiment.sentiment_rating)
        ).join(Response, ResponseSentiment.response_id == Response.id) \
            .join(Employee, Response.employee_id == Employee.id) \
            .filter(Employee.department_id == dept_id) \
            .group_by(ResponseSentiment.field_name).all()

        ai_dict = {row[0]: (row[1] or 0) for row in sentiment_stats}

        # Order keys explicitly to match user_values order
        keys_order = ['role_interest', 'contribution', 'learning', 'feedback',
                      'manager_interaction', 'career_clarity', 'permanence', 'enps_score']

        ai_values = []
        for key in keys_order:
            field_name = DashboardService.METRICS_CONFIG[key]['ai_field']
            ai_values.append(round(ai_dict.get(field_name, 0), 2))

        radar_labels = [DashboardService.METRICS_CONFIG[k]['label'] for k in keys_order]

        return {
            'labels': radar_labels,
            'user_data': user_values,
            'ai_data': ai_values
        }