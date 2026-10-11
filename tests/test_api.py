"""Integration tests for PersonalMail AI FastAPI routes."""

import pytest
from fastapi.testclient import TestClient

from langmail.api.app import app
from langmail.services import TaskService, EmailService
from langmail.storage.database import db_session


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client pointing to temporary database."""
    test_db_path = tmp_path / "test_api_gmail.db"
    monkeypatch.setattr("langmail.config.DB_FILE", test_db_path)
    monkeypatch.setattr("langmail.storage.database.DB_FILE", test_db_path)
    return TestClient(app)


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "metrics" in data


def test_auth_status_endpoint(client):
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    data = res.json()
    assert "authenticated" in data
    assert "model" in data


def test_emails_listing_and_metrics(client):
    # Seed an email
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO messages (
                message_id, thread_id, subject, snippet, from_email, from_name,
                date, is_read, category, priority, requires_reply
            ) VALUES (
                'msg_api_1', 'th_api_1', 'Professor Meeting', 'Let us discuss thesis',
                'prof@university.edu', 'Prof. Smith', '2026-10-08T11:00:00Z', 0, 'college', 'high', 1
            )
            """
        )

    res = client.get("/api/emails")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 1
    assert data["emails"][0]["subject"] == "Professor Meeting"

    # Test single email
    res_single = client.get("/api/emails/msg_api_1")
    assert res_single.status_code == 200
    assert res_single.json()["message_id"] == "msg_api_1"

    # Test metrics
    res_metrics = client.get("/api/metrics")
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    assert metrics["unread"] >= 1
    assert metrics["needs_reply"] >= 1


def test_tasks_endpoints(client):
    # Create task directly
    task = TaskService.create_task(
        thread_id="th_task_1",
        title="Submit Project Report",
        deadline="2026-10-20",
        priority="high"
    )

    # List tasks
    res = client.get("/api/tasks")
    assert res.status_code == 200
    data = res.json()
    assert len(data["tasks"]) == 1

    # Update task status
    res_update = client.patch(f"/api/tasks/{task['id']}", json={"status": "completed"})
    assert res_update.status_code == 200
    assert res_update.json()["status"] == "completed"

    # Delete task
    res_delete = client.delete(f"/api/tasks/{task['id']}")
    assert res_delete.status_code == 200
    assert res_delete.json()["status"] == "deleted"


def test_drafts_endpoints(client):
    res_create = client.post(
        "/api/drafts",
        json={
            "to_email": "candidate@example.com",
            "subject": "Interview Scheduled",
            "body": "Your interview is scheduled for Friday at 3 PM.",
        }
    )
    assert res_create.status_code == 200
    draft = res_create.json()
    assert draft["subject"] == "Interview Scheduled"

    # Update draft
    draft_id = draft["id"]
    res_patch = client.patch(
        f"/api/drafts/{draft_id}",
        json={"body": "Updated interview timing to 4 PM."}
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["body"] == "Updated interview timing to 4 PM."


def test_profile_and_preferences_endpoints(client):
    res = client.get("/api/profile")
    assert res.status_code == 200
    assert res.json()["role"] == "Professional"

    res_put = client.put(
        "/api/profile",
        json={"role": "Senior Engineer", "organization": "AI Labs"}
    )
    assert res_put.status_code == 200
    assert res_put.json()["role"] == "Senior Engineer"

    # Add preference
    res_pref = client.post(
        "/api/profile/preferences",
        json={"pref_type": "signoff", "value": "Warm regards", "confidence": 0.95}
    )
    assert res_pref.status_code == 200
    pref = res_pref.json()
    assert pref["value"] == "Warm regards"

    # List preferences
    res_list = client.get("/api/profile/preferences")
    assert res_list.status_code == 200
    assert len(res_list.json()["preferences"]) >= 1

    # Delete preference
    res_del = client.delete(f"/api/profile/preferences/{pref['id']}")
    assert res_del.status_code == 200
