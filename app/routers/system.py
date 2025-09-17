"""System-level API endpoints."""

import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..models.responses import (
    A2ASendResponse,
    AgentStatusResponse,
    FileData,
    FileListResponse,
    HealthResponse,
    HistoryEntryResponse,
    HistoryItem,
    HistoryListResponse,
    MCPStatusResponse,
    RootResponse,
)
from ..services import AgentManager, HistoryService
from ..utils import get_logger, settings

logger = get_logger(__name__)
router = APIRouter()

_candidate_static_dirs = [
    "/app/static",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "static")),
]
_static_dir = next((d for d in _candidate_static_dirs if os.path.isdir(d)), None)


from ..dependencies import get_agent_manager


def get_history_service() -> HistoryService:
    from ..main import history_service
    return history_service


class A2ASendRequest(BaseModel):
    sender: str
    recipient: str
    message_type: str
    payload: dict[str, Any]
    correlation_id: str | None = None


@router.post("/a2a/send", response_model=A2ASendResponse, tags=["System"])
async def a2a_send(
    request: A2ASendRequest,
    manager: AgentManager = Depends(get_agent_manager),
) -> A2ASendResponse:
    """Deliver an A2A message via HTTP to a recipient agent."""
    result = await manager.receive_a2a_message(
        recipient=request.recipient,
        message_type=request.message_type,
        payload=request.payload,
    )
    return A2ASendResponse(
        status="ok" if "error" not in result else "error",
        result=result,
        correlation_id=request.correlation_id,
    )


@router.get("/", response_model=RootResponse, tags=["System"])
async def root_json() -> RootResponse:
    """Root returns application JSON info (stable for tests)."""
    return RootResponse(
        name=settings.app_name,
        description=settings.description,
        version=settings.app_version,
        environment=settings.environment,
        docs_url="/docs",
        health_url="/health",
        ui_url="/ui" if _static_dir else None,
        timestamp=datetime.utcnow(),
    )


@router.get("/ui", include_in_schema=False)
async def serve_ui():
    """Serve the main UI page if available."""
    if _static_dir:
        index_path = os.path.join(_static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="UI not available")


@router.get("/api", response_model=RootResponse, tags=["System"])
async def root() -> RootResponse:
    """Root API endpoint with application information."""
    return RootResponse(
        name=settings.app_name,
        description=settings.description,
        version=settings.app_version,
        environment=settings.environment,
        docs_url="/docs",
        health_url="/health",
        ui_url="/",
        timestamp=datetime.utcnow(),
    )


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(
    manager: AgentManager = Depends(get_agent_manager),
) -> HealthResponse:
    """Comprehensive health check endpoint."""
    try:
        health_data = await manager.health_check()
        overall_status = "healthy"
        if not health_data.get("agent_manager", {}).get("initialized", False):
            overall_status = "degraded"
        mcp_servers = health_data.get("mcp_servers", {})
        if not all(mcp_servers.values()):
            overall_status = "degraded"
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version=settings.app_version,
            mcp_servers=mcp_servers,
            agents_status={
                agent: data.get("status", "unknown")
                for agent, data in health_data.get("agents", {}).items()
            },
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/api/v1/agents/status", response_model=AgentStatusResponse, tags=["System"])
async def get_agents_status(
    manager: AgentManager = Depends(get_agent_manager),
) -> AgentStatusResponse:
    """Get status of all agents."""
    try:
        health_data = await manager.health_check()
        return AgentStatusResponse(
            agents=health_data.get("agents", {}),
            a2a_service=health_data.get("a2a_service", {}),
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"Failed to get agents status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/mcp/status", response_model=MCPStatusResponse, tags=["System"])
async def get_mcp_status(
    manager: AgentManager = Depends(get_agent_manager),
) -> MCPStatusResponse:
    """Get status of all MCP servers."""
    try:
        health_data = await manager.health_check()
        return MCPStatusResponse(
            mcp_servers=health_data.get("mcp_servers", {}),
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"Failed to get MCP status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/files", response_model=FileListResponse, tags=["System"])
async def list_available_files() -> FileListResponse:
    """List available files in the data directory for @ syntax."""
    import json
    from pathlib import Path

    if settings.environment.lower() == "production":
        return FileListResponse(
            files=[], source="disabled", timestamp=datetime.utcnow()
        )

    try:
        data_dir = Path("/app/data")
        files = []
        if data_dir.exists():
            for json_file in data_dir.rglob("*.json"):
                try:
                    relative_path = json_file.relative_to(data_dir)
                    description = f"Data file: {json_file.name}"
                    try:
                        with open(json_file, encoding="utf-8") as f:
                            content = json.load(f)
                            if isinstance(content, dict):
                                if "Context" in content:
                                    description = content["Context"]
                                elif "description" in content:
                                    description = content["description"]
                    except (json.JSONDecodeError, Exception):
                        description = f"JSON data file: {json_file.name}"
                    files.append(
                        FileData(
                            name=json_file.name,
                            path=str(relative_path),
                            full_path=str(json_file),
                            description=description,
                            size=(json_file.stat().st_size if json_file.exists() else 0),
                        )
                    )
                except Exception as file_error:
                    logger.warning(f"Error processing file {json_file}: {file_error}")
                    continue
        files.sort(key=lambda x: x.name)
        logger.info(f"Found {len(files)} JSON files in data directory")
        return FileListResponse(
            files=files, source="filesystem", timestamp=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        return FileListResponse(
            files=[],
            source="error",
            timestamp=datetime.utcnow(),
            error=str(e),
        )


@router.get("/api/v1/history", response_model=HistoryListResponse, tags=["System"])
async def get_history(
    history: HistoryService = Depends(get_history_service),
) -> HistoryListResponse:
    """Return recent chat/trend entries for the sidebar."""
    items = [
        HistoryItem(
            id=e.id,
            type=e.type,
            title=e.title,
            input=e.input,
            timestamp=datetime.fromisoformat(e.timestamp),
        )
        for e in history.get_recent()
    ]
    return HistoryListResponse(items=items)


@router.get(
    "/api/v1/history/{entry_id}",
    response_model=HistoryEntryResponse,
    tags=["System"],
)
async def get_history_entry(
    entry_id: str,
    history: HistoryService = Depends(get_history_service),
) -> HistoryEntryResponse:
    entry = history.get_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    item = HistoryItem(
        id=entry.id,
        type=entry.type,
        title=entry.title,
        input=entry.input,
        timestamp=datetime.fromisoformat(entry.timestamp),
    )
    return HistoryEntryResponse(item=item, data=entry.data)
