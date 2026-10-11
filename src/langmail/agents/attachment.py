"""PersonalMail AI — Attachment Agent.

Scans incoming email threads, user instructions, or draft bodies for document
requests (e.g. resumes, transcripts, project reports), searches locally indexed
files, and ranks recommendations with confidence and clear reasoning.

Safety Constraint: Never automatically attaches files without explicit user approval.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from langmail.config import settings
from langmail.models.agent_schemas import AttachmentRecommendation, AttachmentSuggestion
from langmail.services.attachment_service import AttachmentService

# Known document categories with canonical labels and trigger synonyms
DOCUMENT_CATEGORIES: dict[str, list[str]] = {
    "resume": ["resume", "cv", "curriculum vitae", "biodata"],
    "project report": ["project report", "btp report", "final report", "technical report", "internship report", "capstone report", "report"],
    "transcript": ["transcript", "grade card", "gradesheet", "marksheet", "academic record", "grade report"],
    "certificate": ["certificate", "certification", "degree", "diploma"],
    "presentation": ["presentation", "slides", "deck", "pitch deck", "slide deck"],
    "portfolio": ["portfolio", "work sample", "case study", "design sample"],
    "proposal": ["proposal", "project proposal", "grant proposal", "research proposal"],
    "contract": ["contract", "agreement", "nda", "offer letter"],
    "invoice": ["invoice", "receipt", "bill"],
    "assignment": ["assignment", "homework", "lab report", "submission"],
}

# Contextual phrases indicating attachment requests or intent
REQUEST_TRIGGER_PATTERNS = [
    # 1. Direct attachment commands: "attach", "want to attach", "also attach", "please attach", etc.
    r"(?:"
    r"(?:(?:i\s+)?(?:want\s+to|demand\s+to|need\s+to|wish\s+to|would\s+like\s+to)\s+)?"
    r"(?:please\s+|kindly\s+|could\s+you\s+(?:please\s+)?|can\s+you\s+(?:please\s+)?|also\s+|and\s+also\s+)?"
    r"(?:attach|attaching|attached|attachment|attachments|include|including)"
    r"(?:\s+(?:also|with|me|herewith|below|is|are|my|the|your|our|a|an|copy\s+of|latest))*"
    r"[:\s]+"
    r")"
    r"([a-zA-Z0-9 _.,&\'/\-()]{2,80}?)"
    r"(?:\s+(?:for|to|asap|by|with|please|in|before|thank|thanks|regards|from)\b|(?:\.|\?|\!)(?:\s|$)|[;?!]|$|[\r\n])",

    # 2. Transfer verbs: "send", "share", "provide", "upload", "forward"
    r"(?:"
    r"(?:please\s+|kindly\s+|could\s+you\s+(?:please\s+)?|can\s+you\s+(?:please\s+)?|would\s+you\s+(?:please\s+)?|also\s+)?"
    r"(?:send|sending|share|sharing|provide|providing|upload|uploading|forward|forwarding)"
    r"(?:\s+(?:me|us|along|across|over|through))?"
    r"(?:\s+(?:your|my|the|a|an|our|copy\s+of|latest))+"
    r"[:\s]+"
    r")"
    r"([a-zA-Z0-9 _.,&\'/\-()]{2,80}?)"
    r"(?:\s+(?:for|to|asap|by|with|please|in|before|thank|thanks|regards|from)\b|(?:\.|\?|\!)(?:\s|$)|[;?!]|$|[\r\n])",

    # 3. Attached notices: "find attached", "attached is", "i have attached"
    r"(?:"
    r"(?:(?:find|sharing|sending)\s+attached|attached\s+(?:is|are|herewith)|i\s+have\s+attached)"
    r"(?:\s+(?:my|the|your|our|a|an|copy\s+of|latest))*"
    r"[:\s]+"
    r")"
    r"([a-zA-Z0-9 _.,&\'/\-()]{2,80}?)"
    r"(?:\s+(?:for|to|asap|by|with|please|in|before|thank|thanks|regards|from)\b|(?:\.|\?|\!)(?:\s|$)|[;?!]|$|[\r\n])",

    # 4. Search requests: "find attachment for", "find my", "locate my"
    r"(?:"
    r"(?:find\s+(?:attachment\s+for|my|the)|locate\s+my)"
    r"(?:\s+(?:my|the|your|our|a|an|copy\s+of|latest))*"
    r"[:\s]+"
    r")"
    r"([a-zA-Z0-9 _.,&\'/\-()]{2,80}?)"
    r"(?:\s+(?:for|to|asap|by|with|please|in|before|thank|thanks|regards|from)\b|(?:\.|\?|\!)(?:\s|$)|[;?!]|$|[\r\n])",
]


class AttachmentAgent:
    """Agent that identifies requested documents and suggests matching local files."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.model

    def detect_requested_documents(
        self,
        text: str,
        thread_context: Optional[str] = None,
    ) -> list[str]:
        """Detect which documents or file types are requested or referenced."""
        combined_text = f"{text or ''}\n{thread_context or ''}".lower()
        detected_requests: list[str] = []

        # 1. Match category synonyms
        for canonical, synonyms in DOCUMENT_CATEGORIES.items():
            for syn in synonyms:
                # Word boundary match
                if re.search(r"\b" + re.escape(syn) + r"\b", combined_text):
                    if canonical not in detected_requests:
                        detected_requests.append(canonical)
                    break

        # 2. Match structural regex patterns for dynamic requests and split conjunctions
        for pat in REQUEST_TRIGGER_PATTERNS:
            matches = re.finditer(pat, combined_text, re.IGNORECASE)
            for m in matches:
                phrase = m.group(1).strip()
                # Split conjunctions like "resume and oslab4" or "resume, oslab4 & report"
                sub_phrases = re.split(r",\s*|\s+(?:and|&)\s+", phrase)
                for sp in sub_phrases:
                    clean_phrase = sp.strip()
                    clean_phrase = re.sub(
                        r"^(?:my|the|your|our|a|an|copy\s+of|latest|also|and)\s+",
                        "",
                        clean_phrase,
                        flags=re.IGNORECASE,
                    ).strip()
                    clean_phrase = re.sub(
                        r"\s+(?:file|files|doc|docs|document|documents|copy|copies)$",
                        "",
                        clean_phrase,
                        flags=re.IGNORECASE,
                    ).strip()
                    if 2 <= len(clean_phrase) <= 35:
                        matched_canonical = None
                        for can, syns in DOCUMENT_CATEGORIES.items():
                            if any(s == clean_phrase or s in clean_phrase for s in syns):
                                matched_canonical = can
                                break
                        target_label = matched_canonical or clean_phrase
                        if target_label not in detected_requests:
                            detected_requests.append(target_label)

        return detected_requests

    def suggest_attachments(
        self,
        text: str,
        thread_context: Optional[str] = None,
        requested_files: Optional[list[str]] = None,
        directory_path: Optional[str] = None,
    ) -> AttachmentRecommendation:
        """Find requested files and return ranked candidate suggestions from the local file index."""
        # 1. Combine explicitly requested files with regex-detected requests
        detected = self.detect_requested_documents(text, thread_context)
        combined_requests: list[str] = []
        for r in (requested_files or []) + detected:
            clean_r = r.strip().lower()
            if clean_r and clean_r not in combined_requests:
                combined_requests.append(clean_r)

        target_requests = combined_requests
        if not target_requests:
            return AttachmentRecommendation(requested_files=[], suggestions=[])

        all_indexed = AttachmentService.list_files(directory_path=directory_path)
        if not all_indexed:
            return AttachmentRecommendation(requested_files=target_requests, suggestions=[])

        # 2. Collect ranked candidates for each requested document independently
        candidates_by_req: dict[str, list[AttachmentSuggestion]] = {}
        for req in target_requests:
            cands = self._rank_files_for_request(req, all_indexed)
            if cands:
                candidates_by_req[req] = cands

        final_suggestions: list[AttachmentSuggestion] = []
        seen_file_ids: set[str] = set()
        seen_filenames: set[str] = set()

        # PASS 1 (Fairness Guarantee):
        # Ensure that every requested document gets its top match represented and pre-selected!
        for req in target_requests:
            cands = candidates_by_req.get(req, [])
            for c in cands:
                clean_fname = c.filename.strip().lower()
                if c.file_id not in seen_file_ids and clean_fname not in seen_filenames:
                    seen_file_ids.add(c.file_id)
                    seen_filenames.add(clean_fname)
                    c.is_selected = False
                    final_suggestions.append(c)
                    break

        # PASS 2 (Second best option per requested document):
        for req in target_requests:
            cands = candidates_by_req.get(req, [])
            for c in cands:
                clean_fname = c.filename.strip().lower()
                if c.file_id not in seen_file_ids and clean_fname not in seen_filenames:
                    seen_file_ids.add(c.file_id)
                    seen_filenames.add(clean_fname)
                    c.is_selected = False
                    final_suggestions.append(c)
                    break

        # PASS 3 (Fill remaining slots up to 8 with highest-confidence alternative candidates):
        remaining: list[AttachmentSuggestion] = []
        for cands in candidates_by_req.values():
            for c in cands:
                clean_fname = c.filename.strip().lower()
                if c.file_id not in seen_file_ids and clean_fname not in seen_filenames:
                    remaining.append(c)

        remaining.sort(key=lambda s: s.confidence, reverse=True)
        for c in remaining:
            if len(final_suggestions) >= 8:
                break
            clean_fname = c.filename.strip().lower()
            if c.file_id not in seen_file_ids and clean_fname not in seen_filenames:
                seen_file_ids.add(c.file_id)
                seen_filenames.add(clean_fname)
                c.is_selected = False
                final_suggestions.append(c)

        return AttachmentRecommendation(
            requested_files=target_requests,
            suggestions=final_suggestions,
        )


    def _rank_files_for_request(
        self,
        requested_item: str,
        files: list[dict[str, Any]],
    ) -> list[AttachmentSuggestion]:
        """Score and formulate reasoning for each candidate file against a requested document."""
        synonyms = [requested_item]
        stem = Path(requested_item).stem.lower()
        if stem and stem != requested_item.lower():
            synonyms.append(stem)

        for can, syn_list in DOCUMENT_CATEGORIES.items():
            if (
                requested_item == can
                or requested_item in syn_list
                or stem == can
                or stem in syn_list
            ):
                synonyms = list(set([can] + syn_list + synonyms))
                break

        norm_req = re.sub(r"[^a-z0-9]", "", requested_item.lower())
        norm_req_stem = re.sub(r"(?:docx|pdf|doc|xlsx|txt|csv|zip)$", "", norm_req) or norm_req

        scored: list[tuple[float, str, dict[str, Any]]] = []

        now_year = datetime.now().year

        for f in files:
            fname = f.get("filename", "").lower()
            tags = (f.get("tags") or "").lower()
            mod_at = f.get("modified_at") or ""
            norm_fname = re.sub(r"[^a-z0-9]", "", fname)
            norm_fname_stem = re.sub(r"(?:docx|pdf|doc|xlsx|txt|csv|zip)$", "", norm_fname) or norm_fname

            base_score = 0.0
            reasons = []

            # 1. Keyword matching
            matched_syn = None
            for s in synonyms:
                if s in fname:
                    matched_syn = s
                    base_score += 0.70
                    break
                elif s in tags:
                    matched_syn = s
                    base_score += 0.60
                    break

            if not matched_syn:
                # Normalized alphanumeric match (handles e.g. "oslab 4" matching "osLab4.docx" or "os_lab_4.docx")
                if (len(norm_req) >= 3 and norm_req in norm_fname) or (
                    len(norm_req_stem) >= 3 and norm_req_stem in norm_fname
                ):
                    matched_syn = requested_item
                    base_score += 0.70
                elif len(norm_fname_stem) >= 3 and norm_fname_stem in norm_req:
                    matched_syn = requested_item
                    base_score += 0.65

            if not matched_syn:
                # Check token overlap
                req_tokens = set(re.findall(r"\w+", requested_item.lower()))
                if len(req_tokens) > 1:
                    req_tokens = {t for t in req_tokens if len(t) > 1}
                file_tokens = set(re.findall(r"\w+", fname))
                overlap = req_tokens.intersection(file_tokens)
                if overlap:
                    base_score += 0.45 * (len(overlap) / max(len(req_tokens), 1))
                    matched_syn = list(overlap)[0]

            if base_score == 0.0:
                continue

            reasons.append(f"Matches '{requested_item}'")

            # 2. Recency boost from filename year (e.g. Resume_2026 vs Resume_2023)
            year_match = re.search(r"(?<!\d)(20[123]\d)(?!\d)", fname)
            if year_match:
                file_year = int(year_match.group(1))
                if file_year >= now_year:
                    base_score += 0.15
                    reasons.append(f"Latest {file_year} edition")
                elif file_year == now_year - 1:
                    base_score += 0.09
                    reasons.append(f"{file_year} edition")
                else:
                    diff = max(1, now_year - file_year)
                    base_score += max(0.01, round(0.15 - (diff * 0.04), 2))
                    reasons.append(f"{file_year} edition")

            # 3. Recency boost from modified_at
            if mod_at:
                try:
                    # ISO parse
                    dt = datetime.fromisoformat(mod_at.replace("Z", "+00:00"))
                    days_old = (datetime.now(timezone.utc) - dt).days
                    if days_old <= 30:
                        base_score += 0.10
                        if "edition" not in " ".join(reasons):
                            reasons.append("Recently updated (<30 days)")
                    elif days_old <= 90:
                        base_score += 0.05
                except Exception:
                    pass

            # 4. Standard format bonus (PDF, DOCX)
            ext = Path(f.get("filename", "")).suffix.lower()
            if ext in [".pdf", ".docx"]:
                base_score += 0.05

            final_confidence = min(0.98, max(0.40, round(base_score, 2)))
            reason_str = " • ".join(reasons)

            scored.append((final_confidence, reason_str, f))

        scored.sort(key=lambda x: (x[0], x[2].get("modified_at", "")), reverse=True)

        suggestions: list[AttachmentSuggestion] = []
        for conf, reason, f in scored:
            dir_p = f.get("directory_path") or str(Path(f["file_path"]).parent)
            suggestions.append(
                AttachmentSuggestion(
                    file_id=f["id"],
                    filename=f["filename"],
                    file_path=f["file_path"],
                    directory_path=dir_p,
                    size_bytes=f.get("size_bytes", 0),
                    mime_type=f.get("mime_type"),
                    confidence=conf,
                    reason=reason,
                    is_selected=False,
                )
            )

        return suggestions

