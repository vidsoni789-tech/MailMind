"""Unit and integration tests for Phase 7: Smart Attachment Workflow."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from langmail.agents.attachment import AttachmentAgent
from langmail.agents.orchestrator import MasterOrchestrator
from langmail.agents.quality import QualityChecker
from langmail.api.app import app
from langmail.models.agent_schemas import IntentType
from langmail.services.attachment_service import AttachmentService
from langmail.storage.database import db_session


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Fixture pointing DB_FILE to a temporary SQLite database."""
    test_db_path = tmp_path / "test_gmail.db"
    monkeypatch.setattr("langmail.config.DB_FILE", test_db_path)
    monkeypatch.setattr("langmail.storage.database.DB_FILE", test_db_path)
    monkeypatch.setattr("langmail.tools.db_tools.DB_FILE", test_db_path)
    return test_db_path


@pytest.fixture(autouse=True)
def clean_db(temp_db):
    """Ensure database has clean state for each test."""
    with db_session() as conn:
        conn.execute("DELETE FROM file_index")
        conn.execute("DELETE FROM drafts")
    yield


@pytest.fixture
def sample_files(tmp_path):
    """Create sample dummy document files for attachment testing."""
    files_dir = tmp_path / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    # 1. Resume 2026 (Newer)
    f_res2026 = files_dir / "Resume_2026.pdf"
    f_res2026.write_text("Vidhansh Resume 2026 - AI Engineer")

    # 2. Resume 2023 (Older)
    f_res2023 = files_dir / "Resume_2023.pdf"
    f_res2023.write_text("Vidhansh Resume 2023")

    # 3. BTP Project Report
    f_report = files_dir / "BTP_Project_Report.docx"
    f_report.write_text("Final BTP Project Technical Report 2026")

    # 4. Transcript
    f_trans = files_dir / "Official_Grade_Card_Transcript.pdf"
    f_trans.write_text("Academic Grade Card Transcript")

    return {
        "dir": files_dir,
        "resume_2026": f_res2026,
        "resume_2023": f_res2023,
        "report": f_report,
        "transcript": f_trans,
    }


# ---------------------------------------------------------------------------
# 1. AttachmentService Tests
# ---------------------------------------------------------------------------

class TestAttachmentService:
    def test_index_file_and_list(self, sample_files):
        f = sample_files["resume_2026"]
        rec = AttachmentService.index_file(str(f), tags="resume, cv")

        assert rec is not None
        assert rec["filename"] == "Resume_2026.pdf"
        assert rec["mime_type"] == "application/pdf"
        assert rec["size_bytes"] > 0
        assert rec["tags"] == "resume, cv"

        all_files = AttachmentService.list_files()
        assert len(all_files) == 1
        assert all_files[0]["id"] == rec["id"]

    def test_scan_directory(self, sample_files):
        indexed = AttachmentService.scan_directory(str(sample_files["dir"]))
        assert len(indexed) == 4

        all_files = AttachmentService.list_files()
        assert len(all_files) == 4

        names = {f["filename"] for f in all_files}
        assert "Resume_2026.pdf" in names
        assert "BTP_Project_Report.docx" in names

    def test_search_candidates(self, sample_files):
        AttachmentService.scan_directory(str(sample_files["dir"]))

        resumes = AttachmentService.search_candidates("resume")
        assert len(resumes) >= 2

        reports = AttachmentService.search_candidates("report")
        assert len(reports) >= 1
        assert reports[0]["filename"] == "BTP_Project_Report.docx"

    def test_delete_file(self, sample_files):
        rec = AttachmentService.index_file(str(sample_files["resume_2026"]))
        assert rec is not None

        deleted = AttachmentService.delete_file(rec["id"], delete_on_disk=False)
        assert deleted is True
        assert len(AttachmentService.list_files()) == 0
        assert sample_files["resume_2026"].exists()


# ---------------------------------------------------------------------------
# 2. AttachmentAgent Tests
# ---------------------------------------------------------------------------

class TestAttachmentAgent:
    @pytest.fixture
    def agent(self):
        return AttachmentAgent()

    def test_detect_requested_documents(self, agent):
        # Explicit request in email
        text1 = "Hi Vidhansh, please send across your resume and project report by tomorrow."
        reqs1 = agent.detect_requested_documents(text1)
        assert "resume" in reqs1
        assert "project report" in reqs1

        # Transcript request
        text2 = "Could you please provide your official transcript or grade card?"
        reqs2 = agent.detect_requested_documents(text2)
        assert "transcript" in reqs2

    def test_suggest_attachments_ranks_newer_higher(self, agent, sample_files):
        # Index all sample files
        AttachmentService.scan_directory(str(sample_files["dir"]))

        recom = agent.suggest_attachments(
            text="Please send over your resume for the interview.",
        )

        assert "resume" in recom.requested_files
        assert len(recom.suggestions) >= 2

        # The 2026 resume MUST rank higher than the 2023 resume
        top_suggestion = recom.suggestions[0]
        assert top_suggestion.filename == "Resume_2026.pdf"
        assert top_suggestion.confidence > 0.85
        assert "2026" in top_suggestion.reason

        second_suggestion = recom.suggestions[1]
        assert second_suggestion.filename == "Resume_2023.pdf"
        assert top_suggestion.confidence >= second_suggestion.confidence

    def test_never_auto_attaches_without_user(self, agent, sample_files):
        AttachmentService.scan_directory(str(sample_files["dir"]))
        recom = agent.suggest_attachments(text="Send your BTP report")

        for sug in recom.suggestions:
            assert sug.is_selected is False


# ---------------------------------------------------------------------------
# 3. QualityChecker Attachment Integration Tests
# ---------------------------------------------------------------------------

class TestQualityCheckerAttachmentIntegration:
    def test_missing_attachment_warning_without_selection(self):
        checker = QualityChecker()
        draft = {
            "to_email": "recruiter@hiring.com",
            "subject": "Application",
            "body": "Dear Hiring Manager,\n\nI have attached my resume for your review.\n\nBest regards,\nVidhansh",
        }

        # No attached files provided -> MISSING_ATTACHMENT warning
        qc = checker.check(draft=draft, attached_files=None)
        assert any(c.code == "MISSING_ATTACHMENT" for c in qc.checks)
        assert qc.status == "WARNING"

    def test_missing_attachment_warning_cleared_when_file_attached(self, sample_files):
        checker = QualityChecker()
        draft = {
            "to_email": "recruiter@hiring.com",
            "subject": "Application",
            "body": "Dear Hiring Manager,\n\nI have attached my resume for your review.\n\nBest regards,\nVidhansh",
        }

        # User approved and checked attachment -> MISSING_ATTACHMENT is resolved
        qc = checker.check(draft=draft, attached_files=[str(sample_files["resume_2026"])])
        assert not any(c.code == "MISSING_ATTACHMENT" for c in qc.checks)


# ---------------------------------------------------------------------------
# 4. Orchestrator Integration Tests
# ---------------------------------------------------------------------------

class TestOrchestratorAttachmentIntegration:
    def test_draft_proposal_includes_attachment_suggestions(self, sample_files):
        AttachmentService.scan_directory(str(sample_files["dir"]))

        orchestrator = MasterOrchestrator()
        result = orchestrator.process_message(
            message="write to recruiter@tech.com saying that I have attached my resume and BTP report"
        )

        assert result.get("draft_card") is not None
        card = result["draft_card"]
        assert "attachment_suggestions" in card
        suggestions = card["attachment_suggestions"]
        assert len(suggestions) >= 1
        filenames = [s["filename"] for s in suggestions]
        assert "Resume_2026.pdf" in filenames

    def test_find_attachment_intent(self, sample_files):
        AttachmentService.scan_directory(str(sample_files["dir"]))

        orchestrator = MasterOrchestrator()
        result = orchestrator.process_message(message="find attachment for my resume")

        assert result["intent"] == IntentType.FIND_ATTACHMENT.value
        assert "Resume_2026.pdf" in result["reply"]


# ---------------------------------------------------------------------------
# 5. FastAPI API Endpoints Tests
# ---------------------------------------------------------------------------

class TestAttachmentApiEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_list_and_scan_endpoints(self, client, sample_files):
        # 1. Scan directory
        scan_res = client.post("/api/files/scan", json={"dir_path": str(sample_files["dir"])})
        assert scan_res.status_code == 200
        scan_data = scan_res.json()
        assert scan_data["newly_indexed"] == 4

        # 2. List files
        list_res = client.get("/api/files")
        assert list_res.status_code == 200
        data = list_res.json()
        assert data["count"] == 4

    def test_suggest_attachments_endpoint(self, client, sample_files):
        AttachmentService.scan_directory(str(sample_files["dir"]))

        res = client.post(
            "/api/attachments/suggest",
            json={"text": "Please provide your project report and grade card"},
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["suggestions"]) >= 1
        filenames = [s["filename"] for s in data["suggestions"]]
        assert any("Report" in f or "Transcript" in f for f in filenames)

    def test_upload_and_delete_endpoints(self, client, tmp_path, monkeypatch):
        # Point FILES_DIR to temp directory
        monkeypatch.setattr("langmail.services.attachment_service.FILES_DIR", tmp_path / "files_upload")

        # Upload
        file_payload = ("test_document.pdf", b"%PDF-1.4 dummy content", "application/pdf")
        upload_res = client.post(
            "/api/files/upload",
            files={"file": file_payload},
            data={"tags": "portfolio, sample"},
        )
        assert upload_res.status_code == 200
        uploaded_data = upload_res.json()
        file_id = uploaded_data["id"]
        assert uploaded_data["filename"] == "test_document.pdf"
        assert uploaded_data["tags"] == "portfolio, sample"

        # Verify listed
        list_res = client.get("/api/files")
        assert any(f["id"] == file_id for f in list_res.json()["files"])

        # Delete
        del_res = client.delete(f"/api/files/{file_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"
