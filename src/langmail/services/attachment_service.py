"""PersonalMail AI — AttachmentService.

Indexes local user files (e.g. resumes, transcripts, reports) and provides
candidate searches for attachment suggestions.
"""

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from langmail.storage.database import db_session

# Default documents folder for PersonalMail AI
FILES_DIR = Path.home() / ".langmail" / "files"

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".txt", ".zip", ".png", ".jpg", ".jpeg", ".csv"
}


class AttachmentService:
    """Service handling local document indexing and candidate file retrieval."""

    @staticmethod
    def ensure_files_dir() -> Path:
        """Create the designated files directory if it doesn't exist."""
        FILES_DIR.mkdir(parents=True, exist_ok=True)
        return FILES_DIR

    @staticmethod
    def index_file(
        file_path: str,
        tags: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Index a single file into the file_index table."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return None

        stat = path.stat()
        file_id = str(uuid.uuid4())
        filename = path.name
        modified_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
        size_bytes = stat.st_size

        # Simple mime determination
        suffix = path.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".ppt": "application/vnd.ms-powerpoint",
            ".txt": "text/plain",
            ".zip": "application/zip",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".csv": "text/csv",
        }
        mime_type = mime_map.get(suffix, "application/octet-stream")
        directory_path = str(path.parent.resolve())

        with db_session() as conn:
            # Upsert by file_path
            conn.execute(
                """
                INSERT INTO file_index (
                    id, file_path, filename, mime_type, size_bytes, modified_at, tags, directory_path, is_current
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(file_path) DO UPDATE SET
                    filename = excluded.filename,
                    size_bytes = excluded.size_bytes,
                    modified_at = excluded.modified_at,
                    tags = COALESCE(excluded.tags, file_index.tags),
                    directory_path = excluded.directory_path,
                    is_current = 1
                """,
                (file_id, str(path.resolve()), filename, mime_type, size_bytes, modified_at, tags, directory_path),
            )

            row = conn.execute(
                "SELECT * FROM file_index WHERE file_path = ?", (str(path.resolve()),)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def scan_directory(dir_path: Optional[str] = None) -> list[dict[str, Any]]:
        """Scan a directory and index all supported documents found within it."""
        target_dir = Path(os.path.expanduser(dir_path)).resolve() if dir_path else AttachmentService.ensure_files_dir()
        if not target_dir.exists() or not target_dir.is_dir():
            return []

        indexed: list[dict[str, Any]] = []
        for root, _, files in os.walk(target_dir):
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    full_p = Path(root) / f
                    res = AttachmentService.index_file(str(full_p))
                    if res:
                        indexed.append(res)

        # Update last_scanned_at and file_count in connected_directories if tracked
        now = datetime.now(timezone.utc).isoformat()
        resolved_str = str(target_dir)
        with db_session() as conn:
            count_row = conn.execute(
                "SELECT COUNT(*) AS count FROM file_index WHERE is_current = 1 AND (directory_path = ? OR file_path LIKE ?)",
                (resolved_str, f"{resolved_str}%"),
            ).fetchone()
            current_count = count_row["count"] if count_row else len(indexed)
            conn.execute(
                """
                UPDATE connected_directories
                SET last_scanned_at = ?, file_count = ?
                WHERE dir_path = ? OR dir_path = ?
                """,
                (now, current_count, resolved_str, str(target_dir.resolve())),
            )

        return indexed

    @staticmethod
    def list_directories() -> list[dict[str, Any]]:
        """List all connected folders and drives with stats."""
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM connected_directories ORDER BY created_at ASC"
            ).fetchall()
            dirs = [dict(r) for r in rows]

            # If no directories exist, seed the default directory
            if not dirs:
                default_p = str(AttachmentService.ensure_files_dir().resolve())
                now = datetime.now(timezone.utc).isoformat()
                dir_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT OR IGNORE INTO connected_directories (
                        id, dir_path, label, is_active, last_scanned_at, file_count, created_at
                    ) VALUES (?, ?, ?, 1, ?, 0, ?)
                    """,
                    (dir_id, default_p, "PersonalMail Default Directory", now, now),
                )
                rows = conn.execute("SELECT * FROM connected_directories").fetchall()
                dirs = [dict(r) for r in rows]

            # Refresh actual file counts
            for d in dirs:
                p_str = d["dir_path"]
                c_row = conn.execute(
                    "SELECT COUNT(*) as count FROM file_index WHERE is_current = 1 AND (directory_path = ? OR file_path LIKE ?)",
                    (p_str, f"{p_str}%"),
                ).fetchone()
                d["file_count"] = c_row["count"] if c_row else 0

            return dirs

    @staticmethod
    def add_directory(dir_path: str, label: Optional[str] = None) -> dict[str, Any]:
        """Connect a new folder or drive path from the user's laptop and scan it immediately."""
        clean_path = dir_path.strip().strip('"').strip("'")
        target_dir = Path(os.path.expanduser(clean_path)).resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            raise ValueError(f"Directory path '{clean_path}' does not exist on your computer.")

        dir_id = str(uuid.uuid4())
        dir_str = str(target_dir)
        now = datetime.now(timezone.utc).isoformat()
        assigned_label = label.strip() if label and label.strip() else (target_dir.name or dir_str)

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO connected_directories (
                    id, dir_path, label, is_active, last_scanned_at, file_count, created_at
                ) VALUES (?, ?, ?, 1, ?, 0, ?)
                ON CONFLICT(dir_path) DO UPDATE SET
                    label = COALESCE(excluded.label, connected_directories.label),
                    is_active = 1
                """,
                (dir_id, dir_str, assigned_label, now, now),
            )

        # Scan right away
        indexed = AttachmentService.scan_directory(dir_str)

        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM connected_directories WHERE dir_path = ?", (dir_str,)
            ).fetchone()
            res = dict(row) if row else {"id": dir_id, "dir_path": dir_str, "label": assigned_label}
            res["indexed_now"] = len(indexed)
            return res

    @staticmethod
    def remove_directory(dir_id: str, unindex_files: bool = True) -> bool:
        """Disconnect a folder and optionally remove indexed file references."""
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM connected_directories WHERE id = ?", (dir_id,)
            ).fetchone()
            if not row:
                return False

            dir_path = row["dir_path"]
            conn.execute("DELETE FROM connected_directories WHERE id = ?", (dir_id,))

            if unindex_files and dir_path:
                conn.execute(
                    "DELETE FROM file_index WHERE directory_path = ? OR file_path LIKE ?",
                    (dir_path, f"{dir_path}%"),
                )

        return True

    @staticmethod
    def scan_all_directories() -> dict[str, Any]:
        """Scan all active connected folders/drives."""
        dirs = AttachmentService.list_directories()
        total_scanned = 0
        newly_indexed = 0
        for d in dirs:
            if d.get("is_active", 1):
                res = AttachmentService.scan_directory(d["dir_path"])
                newly_indexed += len(res)
                total_scanned += 1

        all_files = AttachmentService.list_files()
        return {
            "directories_scanned": total_scanned,
            "newly_indexed": newly_indexed,
            "total_files": len(all_files),
        }

    @staticmethod
    def save_uploaded_file(
        filename: str,
        content: bytes,
        tags: Optional[str] = None,
    ) -> dict[str, Any]:
        """Save raw bytes to ~/.langmail/files/ and automatically index it."""
        files_dir = AttachmentService.ensure_files_dir()
        # Clean filename to avoid path traversal
        safe_filename = Path(filename).name
        target_path = files_dir / safe_filename
        
        with open(target_path, "wb") as f:
            f.write(content)

        indexed = AttachmentService.index_file(str(target_path), tags=tags)
        if not indexed:
            raise RuntimeError(f"Failed to index uploaded file {safe_filename}")
        return indexed

    @staticmethod
    def get_file(file_id: str) -> Optional[dict[str, Any]]:
        """Retrieve indexed file by ID."""
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM file_index WHERE id = ?", (file_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def delete_file(file_id: str, delete_on_disk: bool = False) -> bool:
        """Remove a file from the index, and optionally delete from disk."""
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM file_index WHERE id = ?", (file_id,)
            ).fetchone()
            if not row:
                return False

            file_path = row["file_path"]
            conn.execute("DELETE FROM file_index WHERE id = ?", (file_id,))

        if delete_on_disk and file_path:
            p = Path(file_path)
            if p.exists() and p.is_file():
                try:
                    p.unlink()
                except Exception:
                    pass

        return True

    @staticmethod
    def list_files(directory_path: Optional[str] = None) -> list[dict[str, Any]]:
        """List indexed files ordered by modification time descending, optionally filtered by directory."""
        with db_session() as conn:
            if directory_path:
                clean_dir = str(Path(os.path.expanduser(directory_path.strip())).resolve())
                rows = conn.execute(
                    """
                    SELECT * FROM file_index
                    WHERE is_current = 1 AND (directory_path = ? OR file_path LIKE ?)
                    ORDER BY modified_at DESC
                    """,
                    (clean_dir, f"{clean_dir}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM file_index WHERE is_current = 1 ORDER BY modified_at DESC"
                ).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def search_candidates(keyword: str, directory_path: Optional[str] = None) -> list[dict[str, Any]]:
        """Search files matching a requested document keyword (e.g. 'resume', 'report', 'oslab4', 'oslab 4')."""
        clean_kw = keyword.strip().lower()
        wildcard = f"%{clean_kw}%" if clean_kw else "%"
        no_punct_kw = re.sub(r"[^a-z0-9]", "", clean_kw)
        wildcard_alt = f"%{no_punct_kw}%" if len(no_punct_kw) >= 3 else wildcard

        with db_session() as conn:
            if directory_path:
                clean_dir = str(Path(os.path.expanduser(directory_path.strip())).resolve())
                rows = conn.execute(
                    """
                    SELECT * FROM file_index
                    WHERE is_current = 1
                      AND (directory_path = ? OR file_path LIKE ?)
                      AND (LOWER(filename) LIKE ? OR LOWER(filename) LIKE ? OR LOWER(COALESCE(tags, '')) LIKE ?)
                    ORDER BY modified_at DESC
                    """,
                    (clean_dir, f"{clean_dir}%", wildcard, wildcard_alt, wildcard),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM file_index
                    WHERE is_current = 1
                      AND (LOWER(filename) LIKE ? OR LOWER(filename) LIKE ? OR LOWER(COALESCE(tags, '')) LIKE ?)
                    ORDER BY modified_at DESC
                    """,
                    (wildcard, wildcard_alt, wildcard),
                ).fetchall()
            return [dict(row) for row in rows]

