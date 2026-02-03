import pandas as pd
import logging
import requests
import io
import os

from src.extensions import db
from src.domain.models import Employee, Survey, Response, Department, ResponseSentiment
from src.domain.schemas import EmployeeSchema, SurveyResponseSchema
from src.application.services.sentiment import SentimentAnalysisService

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IngestionService:
    """
        Service responsible for the unified data pipeline.
        It orchestrates Extraction, Loading, and immediate AI Enrichment
        to ensure data consistency (Atomic Operation).
        Supports Upserts (Update if exists, Insert if new).
        """

    DEFAULT_URL = "https://raw.githubusercontent.com/pin-people/tech_playground/refs/heads/main/data.csv"
    DEFAULT_CACHE_PATH = "data.csv"

    @staticmethod
    def run_pipeline(source_url: str = DEFAULT_URL,
                     force_local: bool = False,
                     local_cache_path: str = DEFAULT_CACHE_PATH) -> dict:
        """
        Main entry point. Orchestrates the full ETL + AI lifecycle.

        Args:
            source_url: Remote URL to fetch CSV.
            force_local: If True, skips download and uses local cache.
            local_cache_path: Path to save/load the CSV (Production vs Test isolation).
        """
        logger.info(f"🚀 [Pipeline] Starting ingestion pipeline...")
        stats = {"processed": 0, "updated": 0, "created": 0, "errors": 0, "ai_analyzed": 0}

        try:
            df = IngestionService._load_data(source_url, force_local, local_cache_path)

            IngestionService._process_employees_and_departments(df)
            IngestionService._process_surveys(df)

            ai_stats = IngestionService._process_responses_and_ai(df)

            stats.update(ai_stats)
            stats['processed'] = stats['created'] + stats['updated']

            db.session.commit()

            logger.info(f"✅ [Pipeline] Finished. Stats: {stats}")
            return stats

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ [Pipeline] Critical failure: {str(e)}")
            raise e

    @staticmethod
    def _load_data(url: str, force_local: bool, local_path: str) -> pd.DataFrame:
        """
        Handles data acquisition with a fallback strategy (Network -> Local Cache).
        Writes to the specific 'local_path' to avoid test pollution in prod.
        """
        csv_content = None

        if not force_local:
            try:
                logger.info("📡 [Extract] Downloading data from remote source...")
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                # Update local cache
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)

                csv_content = io.StringIO(response.text)
                logger.info(f"   -> Download successful. Cache updated at {local_path}.")

            except requests.RequestException as e:
                logger.warning(f"   -> Remote fetch failed ({e}). Falling back to local cache.")

        # Fallback to local file
        if csv_content is None:
            if os.path.exists(local_path):
                logger.info(f"📂 [Extract] Loading from local cache: {local_path}")
                csv_content = local_path
            else:
                error_msg = f"Critical: Remote fetch failed and no local cache found at {local_path}."
                raise FileNotFoundError(error_msg)

        # Transform to DataFrame
        return pd.read_csv(csv_content, sep=';', dtype=str).fillna('')

    @staticmethod
    def _process_employees_and_departments(df: pd.DataFrame):
        logger.info("🏗️ [Structural] Syncing Departments and Employees...")
        existing_depts = Department.query.all()
        dept_cache = {d.name: d.id for d in existing_depts}
        existing_employees = Employee.query.all()
        emp_cache = {e.email: e for e in existing_employees}

        for _, row in df.iterrows():
            try:
                # Schema handles alias mapping (e.g., 'nome' -> name)
                emp_dto = EmployeeSchema(**row.to_dict())

                # Dept Sync
                if emp_dto.department not in dept_cache:
                    new_dept = Department(name=emp_dto.department)
                    db.session.add(new_dept)
                    db.session.flush()
                    dept_cache[emp_dto.department] = new_dept.id

                # Employee Sync (Upsert Logic)
                if emp_dto.email in emp_cache:
                    # Update
                    IngestionService._update_employee_fields(emp_cache[emp_dto.email], emp_dto,
                                                             dept_cache[emp_dto.department])
                else:
                    # Create
                    employee = Employee(email=emp_dto.email)
                    IngestionService._update_employee_fields(employee, emp_dto, dept_cache[emp_dto.department])
                    db.session.add(employee)
                    db.session.flush()
                    emp_cache[emp_dto.email] = employee
            except Exception:
                continue

    @staticmethod
    def _process_surveys(df: pd.DataFrame):
        logger.info("📅 [Structural] Syncing Surveys...")
        existing_surveys = Survey.query.all()
        survey_cache = {s.date: s.id for s in existing_surveys}

        for _, row in df.iterrows():
            try:
                row_dict = row.to_dict()
                resp_dto = SurveyResponseSchema(**row_dict)
                survey_date = resp_dto.response_date

                if survey_date not in survey_cache:
                    new_survey = Survey(date=survey_date, name=f"Survey {survey_date.strftime('%m/%Y')}")
                    db.session.add(new_survey)
                    db.session.flush()
                    survey_cache[survey_date] = new_survey.id
            except Exception:
                # Skip invalid rows
                continue

    @staticmethod
    def _process_responses_and_ai(df: pd.DataFrame) -> dict:
        """
        Syncs Responses.
        Logic:
        - If New: Create -> Run AI.
        - If Exists: Check diff -> Update if needed.
          -> If text content changed: Delete old sentiments -> Rerun AI.
        """
        logger.info("🧠 [Transactional] Syncing Responses & Running AI...")

        emp_cache = {e.email: e.id for e in Employee.query.all()}
        survey_cache = {s.date: s.id for s in Survey.query.all()}

        created_count = 0
        updated_count = 0
        skipped_count = 0
        ai_analyzed_count = 0
        errors_count = 0
        processed_batch = 0

        for index, row in df.iterrows():
            try:
                row_dict = row.to_dict()
                resp_dto = SurveyResponseSchema(**row_dict)

                # Resolve FKs
                raw_email = row_dict.get('email')
                emp_id = emp_cache.get(raw_email)
                survey_id = survey_cache.get(resp_dto.response_date)

                if not emp_id or not survey_id:
                    continue

                # Check Existence
                existing_response = Response.query.filter_by(
                    employee_id=emp_id, survey_id=survey_id
                ).first()

                should_run_ai = False
                target_response = None

                if existing_response:
                    # --- UPDATE LOGIC ---
                    has_changes = IngestionService._has_any_changes(existing_response, resp_dto)

                    if not has_changes:
                        skipped_count += 1
                        continue

                    # FIX: Check for text changes BEFORE updating the object!
                    text_changed = IngestionService._has_text_changes(existing_response, resp_dto)

                    # Now update the object in memory
                    IngestionService._update_response_data(existing_response, resp_dto)
                    target_response = existing_response
                    updated_count += 1

                    if text_changed:
                        logger.info(f"   -> Text change detected for Resp {existing_response.id}. Re-running AI.")
                        ResponseSentiment.query.filter_by(response_id=existing_response.id).delete()
                        should_run_ai = True
                else:
                    # --- CREATE LOGIC ---
                    new_response = Response(employee_id=emp_id, survey_id=survey_id)
                    IngestionService._update_response_data(new_response, resp_dto)
                    db.session.add(new_response)
                    target_response = new_response
                    created_count += 1
                    should_run_ai = True

                # --- ATOMIC AI TRIGGER ---
                if should_run_ai:
                    db.session.flush()  # Ensure ID exists
                    SentimentAnalysisService.analyze_response(target_response.id)
                    ai_analyzed_count += 1

                processed_batch += 1

            except Exception as e:
                errors_count += 1
                logger.warning(f"   -> Error on row {index}: {e}")
                continue

        return {
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "ai_analyzed": ai_analyzed_count,
            "errors": errors_count
        }

    # --- Helpers ---

    @staticmethod
    def _update_employee_fields(employee: Employee, dto: EmployeeSchema, dept_id: int):
        employee.name = dto.name
        employee.department_id = dept_id
        employee.corporate_email = dto.corporate_email
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
        if not tenure_str: return 0
        t = tenure_str.lower().strip()
        if "menos de 1" in t: return 1
        if "entre 1 e 2" in t: return 2
        if "entre 2 e 5" in t: return 3
        if "mais de 5" in t: return 4
        return 0

    @staticmethod
    def _update_response_data(response: Response, dto: SurveyResponseSchema):
        """Updates all data fields on a response object from the DTO."""
        response.role_interest = dto.role_interest
        response.contribution = dto.contribution
        response.learning = dto.learning
        response.feedback_score = dto.feedback_score
        response.manager_interaction = dto.manager_interaction
        response.career_clarity = dto.career_clarity
        response.permanence = dto.permanence
        response.enps = dto.enps
        response.role_interest_comment = dto.role_interest_comment
        response.contribution_comment = dto.contribution_comment
        response.learning_comment = dto.learning_comment
        response.feedback_comment = dto.feedback_comment
        response.manager_interaction_comment = dto.manager_interaction_comment
        response.career_clarity_comment = dto.career_clarity_comment
        response.permanence_comment = dto.permanence_comment
        response.enps_comment = dto.enps_comment

    @staticmethod
    def _has_any_changes(response: Response, dto: SurveyResponseSchema) -> bool:
        """Checks if ANY field (metric or text) has changed."""
        metrics = [
            ('role_interest', dto.role_interest),
            ('contribution', dto.contribution),
            ('learning', dto.learning),
            ('feedback_score', dto.feedback_score),
            ('manager_interaction', dto.manager_interaction),
            ('career_clarity', dto.career_clarity),
            ('permanence', dto.permanence),
            ('enps', dto.enps)
        ]
        for attr, val in metrics:
            current = getattr(response, attr)
            if current != val:
                return True

        if IngestionService._has_text_changes(response, dto):
            return True

        return False

    @staticmethod
    def _has_text_changes(response: Response, dto: SurveyResponseSchema) -> bool:
        """Checks if any qualitative text field has changed."""
        fields = [
            ('role_interest_comment', dto.role_interest_comment),
            ('contribution_comment', dto.contribution_comment),
            ('learning_comment', dto.learning_comment),
            ('feedback_comment', dto.feedback_comment),
            ('manager_interaction_comment', dto.manager_interaction_comment),
            ('career_clarity_comment', dto.career_clarity_comment),
            ('permanence_comment', dto.permanence_comment),
            ('enps_comment', dto.enps_comment),
        ]

        for attr, new_val in fields:
            current_val = getattr(response, attr)
            v1 = (current_val or '').strip()
            v2 = (new_val or '').strip()
            if v1 != v2:
                return True
        return False