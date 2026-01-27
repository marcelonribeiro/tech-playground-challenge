from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, Dict, List
from datetime import datetime, date


class EmployeeSchema(BaseModel):
    """
    Schema for validating Employee data coming from the CSV source.
    Maps Portuguese CSV headers to English internal attributes.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Identifiers
    name: str = Field(..., alias='nome')
    email: EmailStr = Field(..., alias='email')
    corporate_email: Optional[str] = Field(None, alias='email_corporativo')

    # Organization
    department: str = Field(..., alias='area')
    role: Optional[str] = Field(None, alias='cargo')
    function: Optional[str] = Field(None, alias='funcao')
    location: Optional[str] = Field(None, alias='localidade')
    tenure: Optional[str] = Field(None, alias='tempo_de_empresa')

    # Demographics
    gender: Optional[str] = Field(None, alias='genero')
    generation: Optional[str] = Field(None, alias='geracao')

    # Hierarchy Levels
    company_level_0: Optional[str] = Field(None, alias='n0_empresa')
    directorate_level_1: Optional[str] = Field(None, alias='n1_diretoria')
    management_level_2: Optional[str] = Field(None, alias='n2_gerencia')
    coordination_level_3: Optional[str] = Field(None, alias='n3_coordenacao')
    area_level_4: Optional[str] = Field(None, alias='n4_area')

    @field_validator('corporate_email', 'role', 'function', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and (v.strip() == '' or v == '-'):
            return None
        return v


class SurveyResponseSchema(BaseModel):
    """
    Schema for validating Survey Response data.
    Handles date parsing and type conversion for metrics.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Metadata
    response_date: date = Field(..., alias='Data da Resposta')

    # Quantitative Metrics (Likert 1-5 / NPS 0-10)
    role_interest: Optional[int] = Field(None, alias='Interesse no Cargo')
    contribution: Optional[int] = Field(None, alias='Contribuição')
    learning: Optional[int] = Field(None, alias='Aprendizado e Desenvolvimento')
    feedback_score: Optional[int] = Field(None, alias='Feedback')
    manager_interaction: Optional[int] = Field(None, alias='Interação com Gestor')
    career_clarity: Optional[int] = Field(None, alias='Clareza sobre Possibilidades de Carreira')
    permanence: Optional[int] = Field(None, alias='Expectativa de Permanência')
    enps: Optional[int] = Field(None, alias='eNPS')

    # Qualitative Comments
    role_interest_comment: Optional[str] = Field(None, alias='Comentários - Interesse no Cargo')
    contribution_comment: Optional[str] = Field(None, alias='Comentários - Contribuição')
    learning_comment: Optional[str] = Field(None, alias='Comentários - Aprendizado e Desenvolvimento')
    feedback_comment: Optional[str] = Field(None, alias='Comentários - Feedback')
    manager_interaction_comment: Optional[str] = Field(None, alias='Comentários - Interação com Gestor')
    career_clarity_comment: Optional[str] = Field(None, alias='Comentários - Clareza sobre Possibilidades de Carreira')
    permanence_comment: Optional[str] = Field(None, alias='Comentários - Expectativa de Permanência')
    enps_comment: Optional[str] = Field(None, alias='[Aberta] eNPS')

    @field_validator('response_date', mode='before')
    @classmethod
    def parse_date(cls, v):
        """Parses DD/MM/YYYY format from CSV."""
        if isinstance(v, str):
            try:
                return datetime.strptime(v, '%d/%m/%Y').date()
            except ValueError:
                raise ValueError(f"Invalid date format: {v}. Expected DD/MM/YYYY")
        return v

    @field_validator('*', mode='before')
    @classmethod
    def handle_empty_values(cls, v):
        """Converts empty strings or hyphens to None for optional fields."""
        if isinstance(v, str) and (v.strip() == '' or v == '-'):
            return None
        return v


class DepartmentResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class EmployeeResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    department: Optional[DepartmentResponse] = None
    role: Optional[str]
    tenure: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class PaginatedEmployeeResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ENPSMetric(BaseModel):
    score: int
    classification: str
    promoters_pct: float
    detractors_pct: float
    passives_pct: float
    total_responses: int


class DashboardStats(BaseModel):
    company_enps: ENPSMetric
    total_employees: int
    participation_rate: float

class SentimentMetric(BaseModel):
    """
    Represents aggregated sentiment data for a specific aspect (e.g., 'Manager Bond').
    """
    field_name: str = Field(..., description="The category of the feedback (e.g., manager_interaction_comment)")
    friendly_label: str = Field(..., description="Human readable label")
    average_rating: float = Field(..., description="Average AI score from 1 to 5")
    sample_size: int = Field(..., description="Number of comments analyzed")

    # Distribution of labels: {'POSITIVE': 15, 'NEGATIVE': 3, 'NEUTRAL': 5}
    distribution: Dict[str, int]


class SentimentOverviewResponse(BaseModel):
    department_id: Optional[int] = None
    metrics: List[SentimentMetric]