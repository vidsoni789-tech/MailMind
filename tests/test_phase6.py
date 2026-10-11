"""Unit and integration tests for Phase 6: Personalization and Edit-Learning Engine."""

import pytest
from fastapi.testclient import TestClient

from langmail.agents.learning import (
    LearningAgent,
    LearnedPreference,
    compute_edit_diff,
    extract_greeting,
    extract_signoff,
)
from langmail.agents.writer import ReplyWriter
from langmail.api.app import app
from langmail.context import assemble_context
from langmail.services import DraftService, ProfileService
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
        conn.execute("DELETE FROM user_edits")
        conn.execute("DELETE FROM style_preferences")
        conn.execute("DELETE FROM drafts")
    yield



# ---------------------------------------------------------------------------
# 1. Edit Diff Computation Tests
# ---------------------------------------------------------------------------

class TestEditDiffComputation:
    def test_greeting_and_signoff_extraction(self):
        body1 = "Dear Dr. Smith,\n\nHere is the report.\n\nBest regards,\nAlex"
        assert extract_greeting(body1) == "Dear Dr. Smith"
        assert extract_signoff(body1) == "Best regards"

        body2 = "Hey John,\n\nThanks for reaching out.\n\nCheers,\nAlex"
        assert extract_greeting(body2) == "Hey John"
        assert extract_signoff(body2) == "Cheers"

    def test_compute_diff_detects_changes(self):
        original = (
            "Dear Dr. Watson,\n\n"
            "I hope this email finds you well. I am writing to provide you with the update.\n\n"
            "Best regards,\nAlex"
        )
        edited = (
            "Hi Dr. Watson,\n\n"
            "Here is the update.\n\n"
            "Cheers,\nAlex"
        )

        diff = compute_edit_diff(original, edited)
        assert diff.greeting_changed is True
        assert diff.original_greeting == "Dear Dr. Watson"
        assert diff.edited_greeting == "Hi Dr. Watson"
        assert diff.signoff_changed is True
        assert diff.original_signoff == "Best regards"
        assert diff.edited_signoff == "Cheers"
        assert diff.length_ratio < 0.7
        assert "I hope this email finds you well" in diff.removed_phrases
        assert "Greeting changed" in diff.diff_summary
        assert "Sign-off changed" in diff.diff_summary


# ---------------------------------------------------------------------------
# 2. Learning Agent Tests
# ---------------------------------------------------------------------------

class TestLearningAgent:
    @pytest.fixture
    def learner(self):
        return LearningAgent()

    def test_extract_greeting_preference(self, learner):
        original = "Dear Sarah,\n\nLet's meet tomorrow.\n\nBest,\nAlex"
        edited = "Hi Sarah,\n\nLet's meet tomorrow.\n\nBest,\nAlex"

        prefs = learner.analyze_edit(original, edited, contact_email="sarah@example.com")
        greeting_prefs = [p for p in prefs if p.pref_type == "greeting"]
        assert len(greeting_prefs) >= 1
        assert greeting_prefs[0].value == "Hi"
        assert greeting_prefs[0].contact_email == "sarah@example.com"
        assert greeting_prefs[0].confidence >= 0.8

    def test_extract_signoff_preference(self, learner):
        original = "Hello Mark,\n\nApproved.\n\nBest regards,\nAlex"
        edited = "Hello Mark,\n\nApproved.\n\nCheers,\nAlex"

        prefs = learner.analyze_edit(original, edited)
        signoff_prefs = [p for p in prefs if p.pref_type == "signoff"]
        assert len(signoff_prefs) >= 1
        assert signoff_prefs[0].value == "Cheers"

    def test_extract_conciseness_and_avoid_phrases(self, learner):
        original = (
            "Hello team,\n\n"
            "I hope this email finds you well. Please feel free to reach out if you have questions. "
            "We wanted to give you a very long and detailed explanation of everything going on this month.\n\n"
            "Regards,\nAlex"
        )
        edited = "Hello team,\n\nMonthly updates are now posted.\n\nRegards,\nAlex"

        prefs = learner.analyze_edit(original, edited)
        types = {p.pref_type for p in prefs}
        assert "conciseness" in types
        assert "avoid_phrase" in types

        avoided_vals = [p.value for p in prefs if p.pref_type == "avoid_phrase"]
        assert "I hope this email finds you well" in avoided_vals
        assert "Please feel free to reach out" in avoided_vals

    def test_learn_from_edit_persists_and_reinforces(self, learner):
        original = "Dear Bob,\n\nHere is the note.\n\nSincerely,\nAlex"
        edited = "Hey Bob,\n\nHere is the note.\n\nCheers,\nAlex"

        # First edit
        learned1 = learner.learn_from_edit(original, edited, contact_email="bob@example.com")
        assert len(learned1) >= 2

        prefs_after_1 = ProfileService.list_preferences(contact_email="bob@example.com")
        greeting_p = next(p for p in prefs_after_1 if p["type"] == "greeting")
        assert greeting_p["evidence_count"] == 1
        assert greeting_p["value"] == "Hey"

        # Second identical edit (reinforcement)
        learned2 = learner.learn_from_edit(original, edited, contact_email="bob@example.com")
        prefs_after_2 = ProfileService.list_preferences(contact_email="bob@example.com")
        greeting_p2 = next(p for p in prefs_after_2 if p["type"] == "greeting")
        assert greeting_p2["evidence_count"] == 2
        assert greeting_p2["confidence"] >= greeting_p["confidence"]


# ---------------------------------------------------------------------------
# 3. ProfileService & Style Preferences Tests
# ---------------------------------------------------------------------------

class TestProfileServicePreferences:
    def test_preference_crud(self):
        # Add
        pref = ProfileService.add_preference(
            pref_type="greeting",
            value="Hi",
            contact_email="contact@client.com",
            confidence=0.85,
        )
        assert pref["id"] is not None
        assert pref["value"] == "Hi"

        # List
        all_p = ProfileService.list_preferences()
        assert len(all_p) == 1

        # Update
        updated = ProfileService.update_preference(pref["id"], value="Hey there", confidence=0.95)
        assert updated is not None
        assert updated["value"] == "Hey there"
        assert updated["confidence"] == 0.95

        # Effective resolution
        effective = ProfileService.get_effective_preferences("contact@client.com")
        assert effective["greeting"] == "Hey there"

        # Delete
        deleted = ProfileService.delete_preference(pref["id"])
        assert deleted is True
        assert len(ProfileService.list_preferences()) == 0

    def test_effective_preferences_prioritizes_contact_over_global(self):
        # Global preference: "Hello"
        ProfileService.add_preference(pref_type="greeting", value="Hello", contact_email=None, confidence=0.9)
        # Contact-specific preference: "Dear Professor"
        ProfileService.add_preference(pref_type="greeting", value="Dear Professor", contact_email="prof@uni.edu", confidence=0.8)

        # For the specific contact, contact-specific greeting wins
        eff_contact = ProfileService.get_effective_preferences("prof@uni.edu")
        assert eff_contact["greeting"] == "Dear Professor"

        # For another contact, global greeting applies
        eff_other = ProfileService.get_effective_preferences("other@random.com")
        assert eff_other["greeting"] == "Hello"

    def test_contact_preferences_strictly_isolated(self):
        # Contact 1 preference (higher confidence)
        ProfileService.add_preference(pref_type="greeting", value="greetings", contact_email="vidhanshji01@gmail.com", confidence=0.95)
        # Contact 2 preference (lower confidence)
        ProfileService.add_preference(pref_type="greeting", value="thankful", contact_email="vidhanshji02@gmail.com", confidence=0.85)

        # Contact 2 MUST get "thankful", NEVER "greetings"
        eff_c2 = ProfileService.get_effective_preferences("vidhanshji02@gmail.com")
        assert eff_c2["greeting"] == "thankful"

        # Contact 1 MUST get "greetings", NEVER "thankful"
        eff_c1 = ProfileService.get_effective_preferences("vidhanshji01@gmail.com")
        assert eff_c1["greeting"] == "greetings"

        # Unknown contact or None MUST NOT inherit contact-specific preferences
        eff_none = ProfileService.get_effective_preferences(None)
        assert eff_none["greeting"] is None

        eff_other = ProfileService.get_effective_preferences("someone_else@gmail.com")
        assert eff_other["greeting"] is None


# ---------------------------------------------------------------------------
# 4. DraftService Integration Tests
# ---------------------------------------------------------------------------

class TestDraftServiceEdits:
    def test_record_edit_computes_diff_and_learns(self):
        draft = DraftService.create_draft(
            to_email="partner@startup.io",
            subject="Collaboration Proposal",
            body="Dear Partner,\n\nI hope this email finds you well. Let's collaborate.\n\nBest regards,\nAlex",
        )

        edit_id, learned = DraftService.record_edit(
            draft_id=draft["id"],
            original_text=draft["body"],
            edited_text="Hi Partner,\n\nLet's collaborate on this initiative.\n\nCheers,\nAlex",
        )

        assert edit_id is not None
        assert len(learned) >= 1

        # Verify edit was stored in user_edits table
        edit_rec = DraftService.get_edit(edit_id)
        assert edit_rec is not None
        assert edit_rec["draft_id"] == draft["id"]
        assert "Greeting changed" in edit_rec["diff_summary"]

        # Verify list_edits
        edits = DraftService.list_edits(draft_id=draft["id"])
        assert len(edits) == 1


# ---------------------------------------------------------------------------
# 5. Context Assembler Injection Tests
# ---------------------------------------------------------------------------

class TestContextAssemblerLearnedStyle:
    def test_context_injects_learned_style_directives(self, monkeypatch):
        # Add learned preferences
        ProfileService.add_preference("greeting", "Hey", contact_email="friend@tech.org")
        ProfileService.add_preference("signoff", "Warmly", contact_email="friend@tech.org")
        ProfileService.add_preference("avoid_phrase", "I hope this email finds you well", contact_email="friend@tech.org")

        # Mock thread fetcher to avoid Gmail API call
        monkeypatch.setattr(
            "langmail.context._fetch_thread",
            lambda tid: {
                "thread_id": tid,
                "subject": "Coffee chat",
                "messages": [{"id": "m1", "from": "friend@tech.org", "date": "2026-10-09", "body": "Free tomorrow?"}],
            },
        )

        files = assemble_context(thread_id="th_xyz", contact_email="friend@tech.org")

        # Check contact profile
        assert "contact_profile.md" in files
        assert "friend@tech.org" in files["contact_profile.md"]
        assert "Learned Preferences for this Contact" in files["contact_profile.md"]
        assert "Hey" in files["contact_profile.md"]

        # Check writing style
        assert "writing_style.md" in files
        assert "Active Writing Style Directives" in files["writing_style.md"]
        assert '**Preferred Greeting:** "Hey"' in files["writing_style.md"]
        assert '**Preferred Sign-off:** "Warmly"' in files["writing_style.md"]
        assert "I hope this email finds you well" in files["writing_style.md"]



# ---------------------------------------------------------------------------
# 6. ReplyWriter Incorporation of Learned Rules
# ---------------------------------------------------------------------------

class TestReplyWriterIncorporation:
    def test_subsequent_draft_incorporates_learned_rules(self):
        # Learn preferences for contact
        ProfileService.add_preference("greeting", "Hi", contact_email="investor@vc.com")
        ProfileService.add_preference("signoff", "Cheers", contact_email="investor@vc.com")
        ProfileService.add_preference("avoid_phrase", "I hope this email finds you well", contact_email="investor@vc.com")

        writer = ReplyWriter(model_name="nonexistent:dummy-model")  # will exercise robust rule-based fallback

        draft = writer.generate_draft(
            instruction="tell them that I hope this email finds you well and our metrics are up 40%",
            recipient="investor@vc.com",
            subject="Q3 Update",
            persist=False,
        )

        assert draft.to_email == "investor@vc.com"
        # Learned greeting applied
        assert draft.body.startswith("Hi,")
        # Learned signoff applied
        assert "Cheers," in draft.body
        # Avoided filler phrase stripped
        assert "I hope this email finds you well" not in draft.body

    def test_draft_generation_extracts_recipient_and_uses_contact_preference(self):
        # Contact 1: "greetings" with higher confidence
        ProfileService.add_preference("greeting", "greetings", contact_email="vidhanshji01@gmail.com", confidence=0.95)
        # Contact 2: "thankful" with lower confidence
        ProfileService.add_preference("greeting", "thankful", contact_email="vidhanshji02@gmail.com", confidence=0.85)

        writer = ReplyWriter(model_name="nonexistent:dummy-model")

        # Instruction explicitly specifies vidhanshji02@gmail.com without passing recipient argument
        draft = writer.generate_draft(
            instruction="write to vidhanshji02@gmail.com for feedback",
            recipient=None,
            persist=False,
        )

        assert draft.to_email == "vidhanshji02@gmail.com"
        # Must strictly use "thankful", NEVER "greetings"
        assert draft.body.startswith("thankful,")
        assert "greetings" not in draft.body


# ---------------------------------------------------------------------------
# 7. FastAPI API Endpoints Tests
# ---------------------------------------------------------------------------

class TestPhase6ApiEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_patch_draft_records_edit_and_learns(self, client):
        draft = DraftService.create_draft(
            to_email="partner@company.com",
            subject="Agreement Draft",
            body="Dear Partner,\n\nI hope this email finds you well. Here is the draft.\n\nBest regards,\nAlex",
        )

        response = client.patch(
            f"/api/drafts/{draft['id']}",
            json={
                "body": "Hi Partner,\n\nHere is the draft.\n\nCheers,\nAlex",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == draft["id"]
        assert "learned_preferences" in data
        assert len(data["learned_preferences"]) >= 1

        # Check edits endpoint
        edits_res = client.get(f"/api/drafts/{draft['id']}/edits")
        assert edits_res.status_code == 200
        edits_data = edits_res.json()
        assert len(edits_data["edits"]) == 1

        # Check global edits endpoint
        all_edits_res = client.get("/api/edits")
        assert all_edits_res.status_code == 200
        assert len(all_edits_res.json()["edits"]) >= 1

    def test_preference_api_endpoints(self, client):
        # 1. Add preference
        add_res = client.post(
            "/api/profile/preferences",
            json={
                "pref_type": "signoff",
                "value": "Warm regards,",
                "confidence": 0.88,
            },
        )
        assert add_res.status_code == 200
        pref = add_res.json()
        pref_id = pref["id"]
        assert pref["value"] == "Warm regards,"

        # 2. List preferences
        list_res = client.get("/api/profile/preferences")
        assert list_res.status_code == 200
        assert len(list_res.json()["preferences"]) >= 1

        # 3. Effective preferences
        eff_res = client.get("/api/profile/preferences/effective")
        assert eff_res.status_code == 200
        assert eff_res.json()["signoff"] == "Warm regards,"

        # 4. Update preference
        put_res = client.put(
            f"/api/profile/preferences/{pref_id}",
            json={"value": "Sincerely,", "confidence": 0.95},
        )
        assert put_res.status_code == 200
        assert put_res.json()["value"] == "Sincerely,"
        assert put_res.json()["confidence"] == 0.95

        # 5. Delete preference
        del_res = client.delete(f"/api/profile/preferences/{pref_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # Verify deleted
        get_again = client.get("/api/profile/preferences")
        assert not any(p["id"] == pref_id for p in get_again.json()["preferences"])
