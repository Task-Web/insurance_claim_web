import mimetypes
import os
import platform
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from mcp.server.fastmcp import FastMCP

from .config import Settings, get_settings
from .file_store import FileStore
from .schemas import (
    ClaimDraft,
    ClaimSubmission,
    ClaimWorkspaceResponse,
    FileMetadata,
    InfoResponse,
    StatePatchRequest,
    StateRequest,
    StateResponse,
)
from .state_store import StateStore

settings = get_settings()
store = StateStore()
file_store = FileStore("files", settings.api_prefix)

tags_metadata = [
    {"name": "claims", "description": "Save drafts and submit insurance claims"},
    {"name": "files", "description": "Upload and fetch files scoped to a user cookie"},
    {"name": "system", "description": "Environment and health information"},
]


def _resolve_user_cookie(provided: Optional[str]) -> str:
    return provided if provided else str(uuid.uuid4())


def _set_user_cookie(response: Response, user_id: str, settings: Settings) -> None:
    response.set_cookie(
        settings.cookie_name,
        user_id,
        max_age=settings.cookie_max_age,
        httponly=False,
        samesite="lax",
    )


# MCP server mirrors REST API operations via Streamable HTTP
mcp_server = FastMCP(
    name=f"{settings.app_name} MCP",
    instructions=(
        "Streamable HTTP MCP interface mirroring the REST API. "
        "Supply user_cookie to reuse the same per-user state; "
        "omit to generate a new cookie-backed state."
    ),
    host="0.0.0.0",
    streamable_http_path="/",
)

mcp_http_app = mcp_server.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MCP session manager so Streamable HTTP transport works when mounted
    mcp_ctx = mcp_server.session_manager.run()
    await mcp_ctx.__aenter__()
    try:
        yield
    finally:
        await mcp_ctx.__aexit__(None, None, None)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    openapi_tags=tags_metadata,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_user_id(
    request: Request, response: Response, settings: Settings = Depends(get_settings)
) -> str:
    cookie_override = request.query_params.get("cookie")
    user_id = cookie_override or request.cookies.get(settings.cookie_name)
    if not user_id:
        user_id = str(uuid.uuid4())
    _set_user_cookie(response, user_id, settings)
    return user_id


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # Minimal middleware that ensures each response carries a request id header.
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    response: JSONResponse = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.get("/health", tags=["system"])
async def health() -> Dict[str, str]:
    return {"status": "ok"}


# when build on the basesite, the below endpoints about state management should remain unchanged
@app.get(
    f"{settings.api_prefix}/state",
    response_model=StateResponse,
    tags=["state"],
    include_in_schema=False,
)
async def get_state(user_id: str = Depends(get_user_id)) -> StateResponse:
    state = await store.get_state(user_id)
    return StateResponse(user_id=user_id, state=state)


@app.put(
    f"{settings.api_prefix}/state",
    response_model=StateResponse,
    tags=["state"],
    summary="Replace state",
    include_in_schema=False,
)
async def put_state(payload: StateRequest, user_id: str = Depends(get_user_id)) -> StateResponse:
    next_state = {"data": payload.data, "note": payload.note}
    if payload.meta is not None:
        next_state["meta"] = payload.meta
    state = await store.replace_state(user_id, next_state)
    return StateResponse(user_id=user_id, state=state)


@app.patch(
    f"{settings.api_prefix}/state",
    response_model=StateResponse,
    tags=["state"],
    summary="Merge into existing state",
    include_in_schema=False,
)
async def patch_state(
    payload: StatePatchRequest, user_id: str = Depends(get_user_id)
) -> StateResponse:
    state = await store.patch_state(user_id, patch=payload.data, note=payload.note)
    return StateResponse(user_id=user_id, state=state)


@app.delete(
    f"{settings.api_prefix}/state",
    response_model=StateResponse,
    tags=["state"],
    summary="Reset and clear state",
    include_in_schema=False,
)
async def delete_state(user_id: str = Depends(get_user_id)) -> StateResponse:
    file_store.delete_user_files(user_id)
    state = await store.reset_state(user_id)
    return StateResponse(user_id=user_id, state=state)


@app.get(
    f"{settings.api_prefix}/claims/workspace",
    response_model=ClaimWorkspaceResponse,
    tags=["claims"],
)
async def get_claim_workspace(user_id: str = Depends(get_user_id)) -> ClaimWorkspaceResponse:
    state = await store.get_state(user_id)
    submitted = state.data.get("submitted_claims")
    return ClaimWorkspaceResponse(
        user_id=user_id,
        draft=state.data.get("current_claim"),
        submitted_claims=submitted if isinstance(submitted, list) else [],
    )


@app.put(f"{settings.api_prefix}/claims/draft", tags=["claims"])
async def save_claim_draft(
    payload: ClaimDraft, user_id: str = Depends(get_user_id)
) -> Dict[str, Any]:
    draft = payload.model_dump(by_alias=True, exclude_none=True)
    draft["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    await store.save_claim_draft(user_id, draft)
    return {"user_id": user_id, "draft": draft}


@app.post(f"{settings.api_prefix}/claims", status_code=201, tags=["claims"])
async def submit_claim(
    payload: ClaimSubmission, user_id: str = Depends(get_user_id)
) -> Dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    claim = {
        "id": f"claim-{uuid.uuid4()}",
        **payload.model_dump(by_alias=True, exclude_none=True),
        "timestamp": timestamp,
        "submittedAt": timestamp,
    }
    await store.submit_claim(user_id, claim)
    return {"user_id": user_id, "claim": claim}


@app.delete(f"{settings.api_prefix}/claims", tags=["claims"])
async def clear_claim_data(user_id: str = Depends(get_user_id)) -> Dict[str, Any]:
    await store.clear_claims(user_id)
    file_store.delete_user_files(user_id)
    return {"user_id": user_id, "cleared": True}


@app.post(
    f"{settings.api_prefix}/files",
    response_model=List[FileMetadata],
    tags=["files"],
    summary="Upload files for the current user",
)
async def upload_files(
    files: List[UploadFile] = File(...), user_id: str = Depends(get_user_id)
) -> List[FileMetadata]:
    return [file_store.save_upload(upload, user_id) for upload in files]


@app.get(
    f"{settings.api_prefix}/files",
    response_model=List[FileMetadata],
    tags=["files"],
    summary="List files for the current user",
)
async def list_files(user_id: str = Depends(get_user_id)) -> List[FileMetadata]:
    return file_store.list_files(user_id)


@app.get(
    f"{settings.api_prefix}/files/{{filename}}",
    tags=["files"],
    summary="Fetch a stored file for the current user",
)
async def get_file(filename: str, user_id: str = Depends(get_user_id)) -> FileResponse:
    target_path = file_store.get_file_path(user_id, filename)
    if not target_path:
        raise HTTPException(status_code=404, detail="File not found")
    display_name = filename.split("__", 1)[1] if "__" in filename else filename
    media_type = mimetypes.guess_type(display_name)[0] or "application/octet-stream"
    response = FileResponse(target_path, media_type=media_type, filename=display_name)
    _set_user_cookie(response, user_id, settings)
    return response


@app.get(
    f"{settings.api_prefix}/info",
    response_model=InfoResponse,
    tags=["system"],
    summary="System and request info",
)
async def info(request: Request, user_id: str = Depends(get_user_id)) -> InfoResponse:
    runtime_env = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "env_mode": os.getenv("ENV", "dev"),
    }
    request_info: Dict[str, Any] = {
        "client": request.client.host if request.client else "unknown",
        "headers": dict(request.headers),
        "path": request.url.path,
        "method": request.method,
        "user_id": user_id,
    }
    return InfoResponse(
        app_name=settings.app_name,
        python_version=runtime_env["python_version"],
        env=runtime_env,
        request=request_info,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request.headers.get("x-request-id")},
    )


@mcp_server.tool(
    name="info",
    description="Return backend environment info and the resolved user id.",
)
async def mcp_info(user_cookie: Optional[str] = None) -> Dict[str, Any]:
    user_id = _resolve_user_cookie(user_cookie)
    runtime_env = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "env_mode": os.getenv("ENV", "dev"),
    }
    return {
        "app_name": settings.app_name,
        "user_id": user_id,
        "env": runtime_env,
    }


# Mount MCP Streamable HTTP app at /mcp for remote access
app.mount("/mcp", mcp_http_app)
