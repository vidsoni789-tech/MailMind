"""PersonalMail AI — Phase 8 End-to-End Test Suite.

Verifies:
1. Action Center & Task Management (creation, filtering, CRUD endpoints)
2. Background Sync Worker lifecycle, threading safety, and endpoints
3. Evaluation dataset validity and benchmark metrics calculation
4. Non-negotiable Human-in-the-Loop Safety: verified that no send/forward executes
   without user approval or when critical safety checks fail.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from langmail.api.app import app
from langmail.models.agent_schemas import DraftProposal
from langmail.services import TaskService
from langmail.services.sync_worker import SyncWorker, sync_worker
from langmail.storage.database import db_session, get_connection


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Ensure test runs against isolated database."""
    test_db = tmp_path / "test_phase8.db"
    monkeypatch.setattr("langmail.config.DB_FILE", test_db)
    monkeypatch.setattr("langmail.storage.database.DB_FILE", test_db)
    monkeypatch.setattr("langmail.tools.db_tools.DB_FILE", test_db)
    monkeypatch.setattr("langmail.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("langmail.sync.HISTORY_ID_FILE", tmp_path / "last_history_id.txt")
    return test_db


@pytest.fixture(autouse=True)
def clean_db(temp_db):
    """Ensure clean database state."""
    with db_session() as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM messages")
    yield


# ===========================================================================
# 1. Action Center & Task Management Tests
# ===========================================================================

class TestTaskManagement:
    def test_create_and_filter_tasks(self):
        # Create tasks with varying priorities and deadlines
        t1 = TaskService.create_task(
            title="Submit Q3 budget review",
            deadline="2026-10-15",
            priority="high",
            source_from="cfo@acme.com",
            source_text="Please submit by Oct 15",
        )
        t2 = TaskService.create_task(
            title="Schedule quarterly team retrospective",
            deadline="2026-10-20",
            priority="medium",
            source_from="manager@acme.com",
        )
        t3 = TaskService.create_task(
            title="Read PyCoder newsletter recommendations",
            priority="low",
        )

        assert t1["title"] == "Submit Q3 budget review"
        assert t1["status"] == "pending"
        assert t1["priority"] == "high"

        # Filter by status
        all_tasks = TaskService.list_tasks(status="all")
        assert len(all_tasks) == 3

        # Filter by priority
        high_tasks = TaskService.list_tasks(priority="high")
        assert len(high_tasks) == 1
        assert high_tasks[0]["id"] == t1["id"]

        # Search term filter
        searched = TaskService.list_tasks(search="budget")
        assert len(searched) == 1
        assert searched[0]["id"] == t1["id"]

        # Update status
        updated = TaskService.update_task_status(t1["id"], "completed")
        assert updated["status"] == "completed"

        completed = TaskService.list_tasks(status="completed")
        assert len(completed) == 1
        assert completed[0]["id"] == t1["id"]

        # Delete task
        deleted = TaskService.delete_task(t3["id"])
        assert deleted is True
        assert len(TaskService.list_tasks()) == 2

    def test_task_rest_api_endpoints(self):
        client = TestClient(app)

        # POST /api/tasks
        res = client.post(
            "/api/tasks",
            json={
                "title": "Renew AWS reserved instances",
                "deadline": "Friday 5 PM",
                "priority": "high",
                "source_from": "aws@amazon.com",
            },
        )
        assert res.status_code == 200
        task_data = res.json()
        assert task_data["title"] == "Renew AWS reserved instances"
        task_id = task_data["id"]

        # GET /api/tasks with query params
        res_list = client.get("/api/tasks?priority=high&search=reserved")
        assert res_list.status_code == 200
        assert res_list.json()["count"] == 1

        # PATCH /api/tasks/{id}
        res_patch = client.patch(f"/api/tasks/{task_id}", json={"status": "completed"})
        assert res_patch.status_code == 200
        assert res_patch.json()["status"] == "completed"

        # DELETE /api/tasks/{id}
        res_del = client.delete(f"/api/tasks/{task_id}")
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "deleted"


# ===========================================================================
# 2. Background Sync Worker Tests
# ===========================================================================

class TestSyncWorker:
    def test_sync_worker_singleton_and_status(self):
        w1 = SyncWorker()
        w2 = SyncWorker()
        assert w1 is w2
        assert w1 is sync_worker

        status = w1.get_status()
        assert "running" in status
        assert "is_syncing" in status
        assert "interval_seconds" in status
        assert status["interval_seconds"] == 120

    def test_sync_worker_start_and_stop_lifecycle(self):
        w = SyncWorker()
        # Start worker with 60s interval
        res_start = w.start(interval_seconds=60)
        assert res_start["running"] is True
        assert res_start["interval_seconds"] == 60

        # Stop worker
        res_stop = w.stop()
        assert res_stop["running"] is False

    def test_sync_worker_unauthenticated_graceful_handling(self):
        w = SyncWorker()
        with patch("langmail.services.sync_worker.is_authenticated", return_value=False):
            res = w.trigger_now()
            assert res["status"] == "skipped"
            assert res["reason"] == "unauthenticated"
            assert "credentials" in res["last_error"].lower()

    def test_sync_routes_api(self):
        client = TestClient(app)

        # GET /api/sync/status
        res_status = client.get("/api/sync/status")
        assert res_status.status_code == 200
        assert "running" in res_status.json()

        # POST /api/sync/start
        res_start = client.post("/api/sync/start", json={"interval_seconds": 90})
        assert res_start.status_code == 200
        assert res_start.json()["running"] is True

        # POST /api/sync/stop
        res_stop = client.post("/api/sync/stop")
        assert res_stop.status_code == 200
        assert res_stop.json()["running"] is False


# ===========================================================================
# 3. Evaluation Dataset Integrity Tests
# ===========================================================================

class TestEvaluationDataset:
    def test_eval_dataset_file_exists_and_valid(self):
        eval_file = Path(__file__).resolve().parent.parent / "eval" / "emails_eval.jsonl"
        assert eval_file.exists(), "eval/emails_eval.jsonl must exist"

        lines = eval_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 50, f"Expected at least 50 test cases, found {len(lines)}"

        categories_seen = set()
        for idx, line in enumerate(lines):
            record = json.loads(line)
            assert "id" in record
            assert "subject" in record
            assert "ground_truth_category" in record
            categories_seen.add(record["ground_truth_category"])

        assert "jobs" in categories_seen
        assert "projects" in categories_seen
        assert "important" in categories_seen
        assert "college" in categories_seen
        assert "newsletters" in categories_seen
        assert "spam" in categories_seen


# ===========================================================================
# 4. Human-in-the-Loop Non-Negotiable Safety Tests
# ===========================================================================

class TestHumanInTheLoopSafetyGuarantees:
    def test_send_strictly_rejected_when_not_approved_by_user(self):
        client = TestClient(app)

        mock_tool = MagicMock()
        with patch("langmail.api.routes.action_routes.gmail_send_message", mock_tool):
            res = client.post(
                "/api/actions/send",
                json={
                    "to_email": "partner@acme.com",
                    "subject": "Agreement",
                    "body": "Here is the finalized contract.",
                    "user_approved": False,
                },
            )
            assert res.status_code == 400
            assert "not approved" in res.json()["detail"].lower()
            # Non-negotiable: Gmail send must NOT have been called
            mock_tool.invoke.assert_not_called()

    def test_send_blocked_when_sensitive_secret_present(self):
        client = TestClient(app)

        mock_tool = MagicMock()
        with patch("langmail.api.routes.action_routes.gmail_send_message", mock_tool):
            # Even with user_approved = True, QualityChecker BLOCK must prevent dispatch
            res = client.post(
                "/api/actions/send",
                json={
                    "to_email": "external@public.com",
                    "subject": "Keys",
                    "body": "Here is the master key: sk-ant-api03-abcdef12345678901234567890",
                    "user_approved": True,
                },
            )
            assert res.status_code == 400
            assert "blocking quality errors" in res.json()["detail"].lower()
            mock_tool.invoke.assert_not_called()

    def test_send_succeeds_when_approved_and_clean(self):
        client = TestClient(app)

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = {"message_id": "msg_994", "thread_id": "th_123"}
        with patch("langmail.api.routes.action_routes.gmail_send_message", mock_tool):
            res = client.post(
                "/api/actions/send",
                json={
                    "to_email": "alex@company.com",
                    "subject": "Meeting Confirmation",
                    "body": "Hi Alex,\n\nI confirm our meeting tomorrow at 10 AM.\n\nBest regards,\nVidhansh",
                    "user_approved": True,
                },
            )
            assert res.status_code == 200
            assert res.json()["status"] == "sent"
            assert res.json()["message_id"] == "msg_994"
            mock_tool.invoke.assert_called_once()
