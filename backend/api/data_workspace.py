"""Local JSON CSV upload endpoints; no multipart dependency or external service."""
import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from backend.services.dataset_workspace import MAX_TOTAL_BYTES, workspace

router = APIRouter(prefix="/api/data", tags=["local data workspace"])


class ActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=32, max_length=32)


@router.get("/workspace")
def describe_workspace():
    return workspace.describe()


@router.post("/validate")
async def validate_dataset(request: Request):
    # Bound the raw body too, including clients using chunked transfer encoding.
    maximum = MAX_TOTAL_BYTES * 2 + 4096
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > maximum:
            raise HTTPException(413, "CSV upload exceeds the supported local request size.")
        chunks.append(chunk)
    try:
        payload = json.loads(b"".join(chunks))
        if not isinstance(payload, dict) or set(payload) != {"files"}:
            raise ValueError()
        files = payload["files"]
        if not isinstance(files, dict) or len(files) > 4 or not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
            raise ValueError()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, "Send a JSON files object containing the four CSV filenames and UTF-8 text.")
    try:
        return await run_in_threadpool(workspace.validate, files)
    except OSError:
        raise HTTPException(503, "RetailIQ could not save the validated local dataset. Check available disk space.")


@router.post("/activate")
def activate_dataset(request: ActivateRequest):
    try:
        return workspace.activate(request.dataset_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/reset")
def reset_dataset():
    return workspace.reset()
