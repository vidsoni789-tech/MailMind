"""PersonalMail AI — Attachment & Document Indexing Routes.

Provides endpoints for browsing indexed documents, scanning directories, uploading files,
and retrieving smart attachment suggestions.
"""

from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from langmail.agents.attachment import AttachmentAgent
from langmail.services.attachment_service import AttachmentService

router = APIRouter(prefix="/api", tags=["attachments"])


class SuggestAttachmentRequest(BaseModel):
    text: str
    thread_context: Optional[str] = None
    requested_files: Optional[list[str]] = None
    directory_path: Optional[str] = None


class IndexFileRequest(BaseModel):
    file_path: str
    tags: Optional[str] = None


class ScanDirectoryRequest(BaseModel):
    dir_path: Optional[str] = None
    scan_all: bool = False


class ConnectDirectoryRequest(BaseModel):
    dir_path: str
    label: Optional[str] = None


@router.get("/directories")
def list_directories():
    """List all connected folders and drives with stats."""
    dirs = AttachmentService.list_directories()
    return {"directories": dirs, "count": len(dirs)}


@router.post("/directories")
def connect_directory(req: ConnectDirectoryRequest):
    """Connect a custom folder or drive from the local machine and index it immediately."""
    try:
        res = AttachmentService.add_directory(dir_path=req.dir_path, label=req.label)
        all_dirs = AttachmentService.list_directories()
        all_files = AttachmentService.list_files()
        return {
            "directory": res,
            "directories": all_dirs,
            "files": all_files,
            "total_files": len(all_files),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect directory: {str(e)}")


@router.delete("/directories/{dir_id}")
def disconnect_directory(dir_id: str, unindex_files: bool = True):
    """Disconnect a custom folder and optionally remove its indexed files."""
    success = AttachmentService.remove_directory(dir_id, unindex_files=unindex_files)
    if not success:
        raise HTTPException(status_code=404, detail="Directory not found")
    all_dirs = AttachmentService.list_directories()
    all_files = AttachmentService.list_files()
    return {
        "status": "disconnected",
        "id": dir_id,
        "directories": all_dirs,
        "files": all_files,
        "total_files": len(all_files),
    }


@router.post("/directories/{dir_id}/scan")
def scan_specific_directory(dir_id: str):
    """Re-scan a specific connected directory by ID."""
    with AttachmentService.ensure_files_dir():
        pass
    dirs = AttachmentService.list_directories()
    target = next((d for d in dirs if d["id"] == dir_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Directory not found")

    indexed = AttachmentService.scan_directory(target["dir_path"])
    all_dirs = AttachmentService.list_directories()
    all_files = AttachmentService.list_files()
    return {
        "newly_indexed": len(indexed),
        "directory": target,
        "directories": all_dirs,
        "files": all_files,
        "total_files": len(all_files),
    }


@router.post("/directories/scan-all")
def scan_all_directories():
    """Scan all connected folders and drives on this machine."""
    res = AttachmentService.scan_all_directories()
    all_dirs = AttachmentService.list_directories()
    return {
        **res,
        "directories": all_dirs,
        "files": res["files"] if "files" in res else AttachmentService.list_files(),
    }


@router.get("/files")
def list_indexed_files(directory_path: Optional[str] = None):
    """List all indexed local files available for attachment suggestions."""
    files = AttachmentService.list_files(directory_path=directory_path)
    return {"files": files, "count": len(files)}


@router.post("/files/scan")
def scan_directory(req: ScanDirectoryRequest = None):
    """Scan local files folder or all connected directories."""
    if req and req.scan_all:
        res = AttachmentService.scan_all_directories()
        return res

    dir_path = req.dir_path if req else None
    indexed = AttachmentService.scan_directory(dir_path)
    all_files = AttachmentService.list_files()
    return {
        "newly_indexed": len(indexed),
        "total_files": len(all_files),
        "files": all_files,
    }


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
):
    """Upload a local document to ~/.langmail/files/ and automatically index it."""
    try:
        content = await file.read()
        res = AttachmentService.save_uploaded_file(
            filename=file.filename,
            content=content,
            tags=tags,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.delete("/files/{file_id}")
def delete_file(file_id: str, delete_disk: bool = True):
    """Remove a file from the index and optionally delete it from disk."""
    success = AttachmentService.delete_file(file_id, delete_on_disk=delete_disk)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "deleted", "id": file_id}


@router.post("/attachments/suggest")
def suggest_attachments(req: SuggestAttachmentRequest):
    """Suggest candidate attachment files based on document requests detected in email/draft."""
    agent = AttachmentAgent()
    recommendation = agent.suggest_attachments(
        text=req.text,
        thread_context=req.thread_context,
        requested_files=req.requested_files,
        directory_path=req.directory_path,
    )
    return recommendation.model_dump()

