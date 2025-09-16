"""Tests for the main FastAPI application."""

from unittest.mock import AsyncMock
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.responses import RepoIntelResponse, TechTrendsResponse
from app.models.schemas import GitHubRepository, RepoMetrics
from app.dependencies import get_agent_manager
from app.services import AgentManager

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)

@pytest.mark.asyncio
async def test_health_check_healthy(client):
    mock_manager = AsyncMock(spec=AgentManager)
    mock_manager.initialized = True
    now_iso = datetime.now(timezone.utc).isoformat()
    mock_manager.health_check.return_value = {
        "agent_manager": {"initialized": True},
        "agents": {
            "entry_agent": {"status": "healthy", "details": "operational", "timestamp": now_iso},
        },
        "mcp_servers": {"brave_search": True},
    }

    app.dependency_overrides[get_agent_manager] = lambda: mock_manager

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_analyze_tech_trends_success(client):
    mock_manager = AsyncMock(spec=AgentManager)
    mock_manager.initialized = True
    now = datetime.now(timezone.utc)
    mock_manager.process_tech_trends_request.return_value = TechTrendsResponse(
        query="FastAPI trends", trends=[], total_items=0, sources=[],
        analysis_timestamp=now, summary="summary"
    )

    app.dependency_overrides[get_agent_manager] = lambda: mock_manager

    response = client.post("/api/v1/trends", json={"query": "FastAPI trends"})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "FastAPI trends"
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_analyze_repositories_success(client):
    mock_manager = AsyncMock(spec=AgentManager)
    mock_manager.initialized = True
    now = datetime.now(timezone.utc)
    mock_manager.process_repo_intel_request.return_value = RepoIntelResponse(
        repositories=[
            GitHubRepository(
                name="fastapi", full_name="tiangolo/fastapi", owner="tiangolo",
                description="FastAPI framework", url="https://github.com/tiangolo/fastapi",
                homepage="https://fastapi.tiangolo.com/", created_at=now, updated_at=now, pushed_at=now,
                metrics=RepoMetrics(stars=1, forks=1, watchers=1, open_issues=1, size=1, default_branch="master", language="Python", last_commit=now, commit_frequency=0.0),
                topics=[], license="MIT", is_fork=False, archived=False
            )
        ],
        total_repos=1,
        analysis_timestamp=now,
        insights="FastAPI is a popular framework",
    )

    app.dependency_overrides[get_agent_manager] = lambda: mock_manager

    response = client.post("/api/v1/repositories", json={"repositories": ["tiangolo/fastapi"]})
    assert response.status_code == 200
    data = response.json()
    assert len(data["repositories"]) == 1
    app.dependency_overrides = {}
