from datetime import datetime
from src.extensions import db


class Department(db.Model):
    """
    Represents a functional area within the company.
    Normalized to avoid redundancy.
    """
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    # INDEX: Critical for aggregation queries (AVG score by Department)
    name = db.Column(db.String(150), unique=True, nullable=False, index=True)

    # Relationships
    employees = db.relationship('Employee', backref='department', lazy='dynamic')

    def __repr__(self):
        return f'<Department {self.name}>'


class Employee(db.Model):
    """
    Represents an employee profile.
    """
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)

    # Identifiers
    # INDEX: Critical for lookups during ingestion (avoid duplicates)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    corporate_email = db.Column(db.String(120))
    phone = db.Column(db.String(50))

    # Organizational Links
    # INDEX: Optimization for JOINs with Department table
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True, index=True)

    role = db.Column(db.String(100))
    function = db.Column(db.String(100))
    location = db.Column(db.String(100))
    tenure = db.Column(db.String(50))
    gender = db.Column(db.String(50))
    generation = db.Column(db.String(50))

    # Hierarchy (Denormalized here for simplicity, or could be separate tables)
    company_level_0 = db.Column(db.String(100))
    directorate_level_1 = db.Column(db.String(100))
    management_level_2 = db.Column(db.String(100))
    coordination_level_3 = db.Column(db.String(100))
    area_level_4 = db.Column(db.String(100))

    # Relationships
    responses = db.relationship('Response', backref='employee', lazy='dynamic')

    def __repr__(self):
        return f'<Employee {self.email}>'


class Survey(db.Model):
    """
    Represents a survey event (e.g., Climate Survey Jan 2026).
    """
    __tablename__ = 'surveys'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), default="Organizational Climate")
    # INDEX: Critical for time-series analysis
    date = db.Column(db.Date, nullable=False, index=True)

    responses = db.relationship('Response', backref='survey', lazy='dynamic')

    def __repr__(self):
        return f'<Survey {self.date}>'


class Response(db.Model):
    """
    Stores individual feedback from an employee for a specific survey.
    """
    __tablename__ = 'responses'

    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    # INDEX: Essential for JOINs
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False, index=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('surveys.id'), nullable=False, index=True)

    # Quantitative Metrics
    role_interest = db.Column(db.Integer)
    contribution = db.Column(db.Integer)
    learning = db.Column(db.Integer)
    feedback_score = db.Column(db.Integer)
    manager_interaction = db.Column(db.Integer)
    career_clarity = db.Column(db.Integer)
    permanence = db.Column(db.Integer)
    enps = db.Column(db.Integer)

    # Qualitative Comments
    role_interest_comment = db.Column(db.Text)
    contribution_comment = db.Column(db.Text)
    learning_comment = db.Column(db.Text)
    feedback_comment = db.Column(db.Text)
    manager_interaction_comment = db.Column(db.Text)
    career_clarity_comment = db.Column(db.Text)
    permanence_comment = db.Column(db.Text)
    enps_comment = db.Column(db.Text)

    # AI & Metadata
    sentiments = db.relationship('ResponseSentiment', backref='response', lazy='dynamic')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Response Emp:{self.employee_id} Survey:{self.survey_id}>'


class ResponseSentiment(db.Model):
    """
    Stores granular sentiment analysis for each comment field in a response.
    Example: field_name='enps_comment', label='NEGATIVE', score=0.98
    """
    __tablename__ = 'response_sentiments'

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey('responses.id', ondelete='CASCADE'), nullable=False, index=True)

    field_name = db.Column(db.String(50), nullable=False)
    sentiment_label = db.Column(db.String(20), nullable=False)
    sentiment_score = db.Column(db.Float, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
