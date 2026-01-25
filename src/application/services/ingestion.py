import pandas as pd
import logging
import requests
import io
import os

from src.extensions import db
from src.domain.models import Employee, Survey, Response, Department
from src.domain.schemas import EmployeeSchema, SurveyResponseSchema

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IngestionService:
    """
    Service responsible for the Extract, Transform, and Load (ETL) process.
    It fetches CSV data, validates it using Pydantic schemas, and persists it
    to the normalized PostgreSQL database.
    """

    DEFAULT_URL = "https://raw.githubusercontent.com/pin-people/tech_playground/refs/heads/main/data.csv"
    LOCAL_BACKUP_PATH = "data.csv"

    @staticmethod
    def process_data(source_url: str = DEFAULT_URL, force_local: bool = False):
        """
        Main entry point for data ingestion with Fallback Strategy.

        Strategy:
        1. Try to fetch from URL (unless force_local is True).
        2. If success: Save content to 'data.csv' (Cache) and use it.
        3. If failure: Warn and try to load from local 'data.csv'.
        4. If local file missing: Raise Critical Error.
        """
        logger.info(f"Starting ingestion process. Target URL: {source_url}")

        csv_content = None

        # Data Acquisition (Fetch w/ Fallback)
        if not force_local:
            try:
                logger.info("Attempting to download data from remote source...")
                response = requests.get(source_url, timeout=30)
                response.raise_for_status()

                # Save to local backup (Cache strategy)
                with open(IngestionService.LOCAL_BACKUP_PATH, 'w', encoding='utf-8') as f:
                    f.write(response.text)

                csv_content = io.StringIO(response.text)
                logger.info("Download successful. Local backup updated.")

            except requests.RequestException as e:
                logger.warning(f"Remote fetch failed: {e}. Attempting fallback to local file.")

        # Fallback Logic
        if csv_content is None:
            if os.path.exists(IngestionService.LOCAL_BACKUP_PATH):
                logger.info(f"Loading data from local backup: {IngestionService.LOCAL_BACKUP_PATH}")
                # Read as file object to match io.StringIO behavior
                csv_content = IngestionService.LOCAL_BACKUP_PATH
            else:
                error_msg = "Critical: Remote fetch failed and no local backup found."
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

        try:
            # Transform (Pandas + Pydantic)
            # Read CSV (forcing string types for safety)
            df = pd.read_csv(csv_content, sep=';', dtype=str)
            df = df.fillna('')

            logger.info(f"CSV Loaded. Rows to process: {len(df)}")

            # Pre-load Caching
            existing_depts = Department.query.all()
            dept_cache = {d.name: d.id for d in existing_depts}

            existing_employees = Employee.query.all()
            emp_cache = {e.email: e for e in existing_employees}

            existing_surveys = Survey.query.all()
            survey_cache = {s.date: s.id for s in existing_surveys}

            processed_count = 0
            errors_count = 0

            # Load & Update
            for index, row in df.iterrows():
                try:
                    row_dict = row.to_dict()

                    # Validation
                    emp_dto = EmployeeSchema(**row_dict)
                    resp_dto = SurveyResponseSchema(**row_dict)

                    # A. Department
                    dept_name = emp_dto.department
                    if dept_name not in dept_cache:
                        new_dept = Department(name=dept_name)
                        db.session.add(new_dept)
                        db.session.flush()
                        dept_cache[dept_name] = new_dept.id

                    dept_id = dept_cache[dept_name]

                    # B. Employee (Full Update)
                    # Calculate Rank
                    if emp_dto.email in emp_cache:
                        employee = emp_cache[emp_dto.email]
                        IngestionService._update_employee_fields(employee, emp_dto, dept_id)
                    else:
                        employee = Employee(
                            email=emp_dto.email,
                            name=emp_dto.name,
                            department_id=dept_id
                            # Other fields set via helper to avoid duplication
                        )
                        IngestionService._update_employee_fields(employee, emp_dto, dept_id)
                        db.session.add(employee)
                        db.session.flush()
                        emp_cache[emp_dto.email] = employee

                    # C. Survey
                    survey_date = resp_dto.response_date
                    if survey_date not in survey_cache:
                        s_name = f"Survey {survey_date.strftime('%m/%Y')}"
                        new_survey = Survey(date=survey_date, name=s_name)
                        db.session.add(new_survey)
                        db.session.flush()
                        survey_cache[survey_date] = new_survey.id

                    survey_id = survey_cache[survey_date]

                    # D. Response
                    existing_response = Response.query.filter_by(
                        employee_id=employee.id,
                        survey_id=survey_id
                    ).first()

                    if not existing_response:
                        new_response = Response(
                            employee_id=employee.id,
                            survey_id=survey_id,
                            role_interest=resp_dto.role_interest,
                            contribution=resp_dto.contribution,
                            learning=resp_dto.learning,
                            feedback_score=resp_dto.feedback_score,
                            manager_interaction=resp_dto.manager_interaction,
                            career_clarity=resp_dto.career_clarity,
                            permanence=resp_dto.permanence,
                            enps=resp_dto.enps,
                            role_interest_comment=resp_dto.role_interest_comment,
                            contribution_comment=resp_dto.contribution_comment,
                            learning_comment=resp_dto.learning_comment,
                            feedback_comment=resp_dto.feedback_comment,
                            manager_interaction_comment=resp_dto.manager_interaction_comment,
                            career_clarity_comment=resp_dto.career_clarity_comment,
                            permanence_comment=resp_dto.permanence_comment,
                            enps_comment=resp_dto.enps_comment
                        )
                        db.session.add(new_response)

                    processed_count += 1

                    if processed_count % 100 == 0:
                        db.session.commit()

                except Exception as row_error:
                    errors_count += 1
                    logger.warning(f"Skipping invalid row {index}: {str(row_error)}")
                    continue

            db.session.commit()
            logger.info(f"Ingestion Finished. Processed: {processed_count}, Errors: {errors_count}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Critical Ingestion Error: {str(e)}")
            raise e

    @staticmethod
    def _update_employee_fields(employee: Employee, dto: EmployeeSchema, dept_id: int):
        """
        Helper method to update all employee fields from DTO.
        Ensures strict synchronization between CSV source and Database.
        """
        employee.name = dto.name
        employee.corporate_email = dto.corporate_email
        employee.phone = dto.phone
        employee.department_id = dept_id
        employee.role = dto.role
        employee.function = dto.function
        employee.location = dto.location
        employee.tenure = dto.tenure
        employee.tenure_rank = IngestionService._calculate_tenure_rank(dto.tenure)
        employee.gender = dto.gender
        employee.generation = dto.generation
        employee.company_level_0 = dto.company_level_0
        employee.directorate_level_1 = dto.directorate_level_1
        employee.management_level_2 = dto.management_level_2
        employee.coordination_level_3 = dto.coordination_level_3
        employee.area_level_4 = dto.area_level_4

    @staticmethod
    def _calculate_tenure_rank(tenure_str: str) -> int:
        """
        Maps tenure string to an ordinal integer for sorting.
        Categories:
        1: < 1 year
        2: 1-2 years
        3: 2-5 years
        4: > 5 years
        """
        if not tenure_str:
            return 0

        t = tenure_str.lower().strip()

        # Ordem lógica de verificação
        if "menos de 1" in t: return 1
        if "entre 1 e 2" in t: return 2
        if "entre 2 e 5" in t: return 3
        if "mais de 5" in t: return 4

        return 0  # Caso não bata com nada (Fallback)