"""PersonalMail AI — EmailService.

Provides high-level data access for email metadata, threads, filtering,
and triage status.
"""

from typing import Any, Optional
from langmail.storage.database import db_session


class EmailService:
    """Service handling email metadata querying, categorization, and thread retrieval."""

    @staticmethod
    def list_emails(
        unread_only: bool = False,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        requires_reply: Optional[bool] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List emails with flexible filtering."""
        query = "SELECT * FROM messages WHERE 1=1"
        params: list[Any] = []

        if unread_only:
            query += " AND is_read = 0"
        if category and category.lower() != "all":
            query += " AND category = ?"
            params.append(category.lower())
        if priority and priority.lower() != "all":
            query += " AND priority = ?"
            params.append(priority.lower())
        if requires_reply is not None:
            query += " AND requires_reply = ?"
            params.append(1 if requires_reply else 0)
        if search_query:
            query += " AND (subject LIKE ? OR snippet LIKE ? OR from_name LIKE ? OR from_email LIKE ?)"
            wildcard = f"%{search_query}%"
            params.extend([wildcard, wildcard, wildcard, wildcard])

        query += " ORDER BY date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with db_session() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_email(message_id: str) -> Optional[dict[str, Any]]:
        """Fetch single email metadata."""
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE message_id = ?", (message_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_thread(thread_id: str) -> list[dict[str, Any]]:
        """Fetch all indexed messages belonging to a thread."""
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE thread_id = ? ORDER BY date ASC",
                (thread_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_triage(
        message_id: str,
        category: str,
        priority: str,
        requires_reply: bool,
        security_risk: str = "safe",
        reason: Optional[str] = None,
    ) -> None:
        """Update triage classifications for a message."""
        with db_session() as conn:
            conn.execute(
                """
                UPDATE messages
                SET category = ?, priority = ?, requires_reply = ?, security_risk = ?, triage_reason = ?
                WHERE message_id = ?
                """,
                (
                    category.lower(),
                    priority.lower(),
                    1 if requires_reply else 0,
                    security_risk.lower(),
                    reason,
                    message_id,
                ),
            )

    @staticmethod
    def mark_read(message_id: str, is_read: bool = True) -> None:
        """Mark email as read or unread in the local database."""
        with db_session() as conn:
            conn.execute(
                "UPDATE messages SET is_read = ? WHERE message_id = ?",
                (1 if is_read else 0, message_id),
            )

    @staticmethod
    def get_inbox_metrics() -> dict[str, int]:
        """Return counts for dashboard badges."""
        with db_session() as conn:
            total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            unread = conn.execute("SELECT COUNT(*) FROM messages WHERE is_read = 0").fetchone()[0]
            needs_reply = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE requires_reply = 1 AND is_read = 0"
            ).fetchone()[0]
            high_priority = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE priority IN ('urgent', 'high') AND is_read = 0"
            ).fetchone()[0]
            security_alerts = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE security_risk IN ('caution', 'danger')"
            ).fetchone()[0]

            return {
                "total": total,
                "unread": unread,
                "needs_reply": needs_reply,
                "high_priority": high_priority,
                "security_alerts": security_alerts,
            }

    @staticmethod
    def count_emails() -> int:
        """Return total email count in local database."""
        with db_session() as conn:
            return conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    @staticmethod
    def classify_metadata(
        subject: str,
        snippet: str,
        from_email: str,
        from_name: str,
        labels: Any = None,
    ) -> dict[str, Any]:
        """Fast heuristic triage classifier for category, priority, and reply requirement."""
        subj_lower = (subject or "").lower()
        snip_lower = (snippet or "").lower()
        from_e_lower = (from_email or "").lower()
        from_n_lower = (from_name or "").lower()
        text = f"{subj_lower} {snip_lower} {from_e_lower} {from_n_lower}"

        # Category
        cat = "other"
        job_keywords = [
            "interview", "job", "application", "career", "recruiter", "hiring",
            "offer", "internship", "unstop", "naukri", "indeed", "resume",
            "linkedin", "glassdoor", "wellfound", "hired", "talent", "opportunity",
            "fellowship", "assessment", "candidate", "fellow"
        ]
        college_keywords = [
            "college", "university", "campus", "exam", "faculty", "professor",
            "assignment", "lecture", "student", "dean", "attendance", "syllabus",
            ".edu", ".ac.in", "semester", "grade", "coursera", "edx", "thesis",
            "registrar", "fafsa", "gradescope", "bookstore", "hackathon", "library",
            "ddia", "circulation"
        ]
        finance_keywords = [
            "bank", "statement", "transaction", "otp", "invoice", "receipt",
            "payment", "bill", "canarabank", "hdfc", "sbi", "icici", "axis",
            "credit card", "debit card", "account alert", "wallet", "upi",
            "lease renewal", "rent", "insurance", "turbotax", "tax payment", "irs",
            "chase", "apartment", "policy", "direct pay"
        ]
        project_keywords = [
            "github", "commit", "pull request", "pr #", "pipeline", "ci/cd",
            "deployment", "staging", "cluster", "postgres", "migration",
            "roadmap", "sentry", "docker", "kubernetes", "bug", "refactor",
            "architecture", "repo", "merge", "devops", "api integration", "deadlock"
        ]
        spam_keywords = [
            "lottery", "prize", "wire transfer", "kyc verification", "seed phrase",
            "helpdesk-auth", "customs fee", "unpaid customs", "profile 6 times today",
            "verify credentials immediately", "password expired", "euromillions", "claim your prize"
        ]
        newsletter_keywords = [
            "newsletter", "digest", "weekly", "noreply", "no-reply", "marketing",
            "updates", "aimlabs", "kaggle", "medium.com", "substack", "daily",
            "announcement", "mailer", "promotions", "discount", "sale", "tldr",
            "morning brew", "deal", "deals", "off your", "product hunt", "pycoder"
        ]

        # Security Risk
        sec_risk = "safe"
        if any(w in text for w in [
            "verify your password", "account suspended", "unusual sign-in",
            "compromised", "urgent action required to keep account", "reset password",
            "2-step verification", "seed phrase", "wire transfer", "wire $", "kyc verification",
            "password expired", "click http", "helpdesk-auth"
        ]):
            sec_risk = "phishing" if any(p in text for p in ["seed phrase", "wire", "password expired", "click http", "kyc", "helpdesk"]) else "caution"

        if sec_risk != "safe" or any(w in text for w in spam_keywords):
            cat = "spam"
        elif any(w in text for w in job_keywords):
            cat = "job"
        elif any(w in text for w in project_keywords):
            cat = "projects"
        elif any(w in text for w in college_keywords):
            cat = "college"
        elif any(w in text for w in finance_keywords):
            cat = "finance"
        elif any(w in text for w in newsletter_keywords):
            cat = "newsletter"
        elif any(w in text for w in ["hi vidhansh", "hey vidhansh", "dear vidhansh"]) or (
            from_e_lower.endswith("@gmail.com") and "no-reply" not in from_e_lower and "noreply" not in from_e_lower
        ):
            cat = "personal"

        # Priority
        prio = "medium"
        urgent_words = [
            "urgent", "action required", "immediate", "asap", "deadline",
            "final notice", "critical", "important alert", "security alert"
        ]
        if any(w in subj_lower for w in urgent_words) or sec_risk != "safe":
            prio = "high"
        elif cat == "newsletter":
            prio = "low"
        elif cat in ["job", "finance"] and any(w in text for w in ["interview scheduled", "offer letter", "assessment test", "due today", "payment due"]):
            prio = "high"

        # Requires reply
        req_reply = False
        reply_words = [
            "please confirm", "let me know", "are you available", "can you",
            "rsvp", "kindly reply", "reply to this", "confirm your attendance",
            "please share", "send your resume", "revert back"
        ]
        if any(w in text for w in reply_words) and cat not in ["newsletter"]:
            req_reply = True

        return {
            "category": cat,
            "priority": prio,
            "requires_reply": req_reply,
            "security_risk": sec_risk,
        }

    @staticmethod
    def triage_all_emails(force: bool = False) -> int:
        """Batch classify emails in the local database."""
        with db_session() as conn:
            query = "SELECT message_id, subject, snippet, from_email, from_name, labels FROM messages"
            if not force:
                query += " WHERE category = 'other' AND priority = 'medium'"
            rows = conn.execute(query).fetchall()

            count = 0
            for r in rows:
                triage = EmailService.classify_metadata(
                    subject=r["subject"] or "",
                    snippet=r["snippet"] or "",
                    from_email=r["from_email"] or "",
                    from_name=r["from_name"] or "",
                    labels=r["labels"] or "",
                )
                conn.execute(
                    """
                    UPDATE messages
                    SET category = ?, priority = ?, requires_reply = ?, security_risk = ?
                    WHERE message_id = ?
                    """,
                    (
                        triage["category"],
                        triage["priority"],
                        1 if triage["requires_reply"] else 0,
                        triage["security_risk"],
                        r["message_id"],
                    ),
                )
                count += 1
            return count
