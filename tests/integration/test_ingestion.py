import pytest
import os
from unittest.mock import patch, MagicMock
from src.application.services.ingestion import IngestionService
from src.domain.models import Employee, Department, Survey, Response, ResponseSentiment

# Sample CSV Content (Same as before)
CSV_CONTENT_V1 = """email;nome;email_corporativo;celular;area;cargo;funcao;localidade;tempo_de_empresa;genero;geracao;n0_empresa;n1_diretoria;n2_gerencia;n3_coordenacao;n4_area;Data da Resposta;Interesse no Cargo;Contribuição;Aprendizado e Desenvolvimento;Feedback;Interação com Gestor;Clareza sobre Possibilidades de Carreira;Expectativa de Permanência;eNPS;Comentários - Interesse no Cargo;Comentários - Contribuição;Comentários - Aprendizado e Desenvolvimento;Comentários - Feedback;Comentários - Interação com Gestor;Comentários - Clareza sobre Possibilidades de Carreira;Comentários - Expectativa de Permanência;[Aberta] eNPS
john.doe@pin.com;John Doe;john.doe@pin.com;;Engineering;Dev;Dev;Remote;Entre 1 e 2;;;Emp;Dir;Ger;Coord;Area;01/01/2022;5;5;5;5;5;5;5;10;;;;;;;;Great place!"""

CSV_CONTENT_V2_SCORE_CHANGE = """email;nome;email_corporativo;celular;area;cargo;funcao;localidade;tempo_de_empresa;genero;geracao;n0_empresa;n1_diretoria;n2_gerencia;n3_coordenacao;n4_area;Data da Resposta;Interesse no Cargo;Contribuição;Aprendizado e Desenvolvimento;Feedback;Interação com Gestor;Clareza sobre Possibilidades de Carreira;Expectativa de Permanência;eNPS;Comentários - Interesse no Cargo;Comentários - Contribuição;Comentários - Aprendizado e Desenvolvimento;Comentários - Feedback;Comentários - Interação com Gestor;Comentários - Clareza sobre Possibilidades de Carreira;Comentários - Expectativa de Permanência;[Aberta] eNPS
john.doe@pin.com;John Doe;john.doe@pin.com;;Engineering;Dev;Dev;Remote;Entre 1 e 2;;;Emp;Dir;Ger;Coord;Area;01/01/2022;1;1;1;1;1;1;1;0;;;;;;;;Great place!"""

CSV_CONTENT_V3_TEXT_CHANGE = """email;nome;email_corporativo;celular;area;cargo;funcao;localidade;tempo_de_empresa;genero;geracao;n0_empresa;n1_diretoria;n2_gerencia;n3_coordenacao;n4_area;Data da Resposta;Interesse no Cargo;Contribuição;Aprendizado e Desenvolvimento;Feedback;Interação com Gestor;Clareza sobre Possibilidades de Carreira;Expectativa de Permanência;eNPS;Comentários - Interesse no Cargo;Comentários - Contribuição;Comentários - Aprendizado e Desenvolvimento;Comentários - Feedback;Comentários - Interação com Gestor;Comentários - Clareza sobre Possibilidades de Carreira;Comentários - Expectativa de Permanência;[Aberta] eNPS
john.doe@pin.com;John Doe;john.doe@pin.com;;Engineering;Dev;Dev;Remote;Entre 1 e 2;;;Emp;Dir;Ger;Coord;Area;01/01/2022;1;1;1;1;1;1;1;0;;;;;;;;Terrible place!"""


class TestIngestionService:
    """
    Level 1 Tests: Data Pipeline & Integrity.
    Uses a temporary cache file to avoid polluting production data.csv.
    """

    @pytest.fixture
    def test_cache_path(self, tmp_path):
        """Creates a temporary file path for the CSV cache."""
        # tmp_path is a built-in pytest fixture that creates a unique temp directory
        return str(tmp_path / "test_data.csv")

    @patch('src.application.services.ingestion.requests.get')
    @patch('src.application.services.ingestion.SentimentAnalysisService.analyze_response')
    def test_run_pipeline_fresh_ingestion(self, mock_analyze, mock_get, db_session, test_cache_path):
        """
        GIVEN a fresh database and valid CSV data
        WHEN run_pipeline is called with a custom test cache path
        THEN it should populate entities and NOT overwrite the main data.csv
        """
        # 1. Arrange: Mock CSV download
        mock_response = MagicMock()
        mock_response.text = CSV_CONTENT_V1
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # 2. Act: Pass the test_cache_path!
        stats = IngestionService.run_pipeline(
            source_url="http://mock.com",
            local_cache_path=test_cache_path
        )

        # 3. Assert - Statistics
        assert stats['created'] == 1
        assert stats['ai_analyzed'] == 1

        # 4. Assert - File Isolation
        # Verify that the test file was created
        assert os.path.exists(test_cache_path)
        # Verify content match
        with open(test_cache_path, 'r') as f:
            assert "Great place!" in f.read()

    @patch('src.application.services.ingestion.requests.get')
    @patch('src.application.services.ingestion.SentimentAnalysisService.analyze_response')
    def test_run_pipeline_idempotency(self, mock_analyze, mock_get, db_session, test_cache_path):
        """
        GIVEN data already ingested
        WHEN run_pipeline is called again with IDENTICAL data
        THEN it should skip updates
        """
        # 1. Arrange: Run V1 once
        mock_response = MagicMock()
        mock_response.text = CSV_CONTENT_V1
        mock_get.return_value = mock_response
        IngestionService.run_pipeline(local_cache_path=test_cache_path)

        mock_analyze.reset_mock()

        # 2. Act: Run V1 again
        stats = IngestionService.run_pipeline(local_cache_path=test_cache_path)

        # 3. Assert
        assert stats['skipped'] == 1
        assert stats['ai_analyzed'] == 0
        mock_analyze.assert_not_called()

    @patch('src.application.services.ingestion.requests.get')
    @patch('src.application.services.ingestion.SentimentAnalysisService.analyze_response')
    def test_run_pipeline_update_text_trigger_ai(self, mock_analyze, mock_get, db_session, test_cache_path):
        """
        GIVEN data already ingested
        WHEN run_pipeline is called with CHANGED TEXT
        THEN it should update the record AND trigger AI re-analysis
        """
        # 1. Arrange: Run V1
        mock_response = MagicMock()
        mock_response.text = CSV_CONTENT_V1
        mock_get.return_value = mock_response
        IngestionService.run_pipeline(local_cache_path=test_cache_path)

        # 2. Act: Run V3 (Text changed)
        mock_response.text = CSV_CONTENT_V3_TEXT_CHANGE
        mock_analyze.reset_mock()

        stats = IngestionService.run_pipeline(local_cache_path=test_cache_path)

        # 3. Assert
        assert stats['updated'] == 1
        assert stats['ai_analyzed'] == 1  # Must re-run AI

        resp = Response.query.first()
        assert resp.enps_comment == "Terrible place!"

        mock_analyze.assert_called_with(resp.id)

    @patch('src.application.services.ingestion.requests.get')
    def test_run_pipeline_rollback_on_error(self, mock_get, db_session, test_cache_path):
        """
        GIVEN a critical error occurs
        WHEN run_pipeline executes
        THEN it should rollback
        """
        mock_response = MagicMock()
        mock_response.text = CSV_CONTENT_V1
        mock_get.return_value = mock_response

        # Force error
        with patch('src.application.services.ingestion.IngestionService._process_surveys',
                   side_effect=Exception("DB Dead")):
            with pytest.raises(Exception):
                IngestionService.run_pipeline(local_cache_path=test_cache_path)

        assert Response.query.count() == 0