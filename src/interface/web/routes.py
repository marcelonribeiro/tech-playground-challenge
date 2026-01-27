from flask import render_template, request
from src.application.services.dashboard_service import DashboardService
from . import web_bp


@web_bp.route('/')
def index():
    """
    Task 2: Executive Dashboard.
    Delegates logic to DashboardService.
    """
    dept_id = request.args.get('dept_id', type=int)
    role = request.args.get('role', type=str)

    data = DashboardService.get_overview_data(dept_id, role)

    return render_template(
        'dashboard.html',
        active_page='overview',
        selected_dept_id=dept_id,
        selected_role=role,
        **data  # Unpack dictionary: departments, roles, view_context, metrics, chart_data
    )


@web_bp.route('/company')
def company_view():
    """
    Task 6: Company Level Visualization.
    Delegates logic to DashboardService.
    """
    data = DashboardService.get_company_deep_dive_data()

    return render_template(
        'company.html',
        active_page='company',
        **data  # Unpack: metrics, charts
    )


@web_bp.route('/areas')
def areas_view():
    """
    Task 7: Area Level Visualization.
    Delegates logic to DashboardService.
    """
    dept_id = request.args.get('dept_id', type=int)
    metric_key = request.args.get('metric', 'role_interest')

    data = DashboardService.get_area_intelligence_data(dept_id, metric_key)

    return render_template(
        'areas.html',
        active_page='areas',
        selected_dept_id=dept_id,
        selected_metric=metric_key,
        **data # Unpack: departments, metrics_options, selected_metric_label, comparison, deep_dive
    )


@web_bp.route('/employees')
def employees_view():
    """
    Task 8: Employee Level Visualization.
    Delegates logic to DashboardService.
    """
    emp_id = request.args.get('emp_id', type=int)

    data = DashboardService.get_employee_profile_data(emp_id)

    return render_template(
        'employees.html',
        active_page='employees',
        selected_emp_id=emp_id,
        **data # Unpack: search_list, employee, chart_config
    )


@web_bp.route('/api-docs')
def api_docs():
    """
    Renders the API Documentation page.
    Static render, no service needed.
    """
    return render_template('api_docs.html', active_page='api_docs')