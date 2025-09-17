"""Analysis-related API endpoints (trends, repositories)."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from ..models.requests import (
    CombinedAnalysisRequest,
    RepoIntelRequest,
    TechTrendsRequest,
)
from ..models.responses import (
    CombinedAnalysisResponse,
    RepoIntelResponse,
    TechTrendsResponse,
)
from ..services import AgentManager
from ..utils import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Analysis"])


from ..dependencies import get_agent_manager


@router.post("/trends", response_model=TechTrendsResponse)
async def analyze_tech_trends(
    request: TechTrendsRequest,
    manager: AgentManager = Depends(get_agent_manager),
) -> TechTrendsResponse:
    """Analyze technology trends using Entry Agent."""
    logger.info(f"Tech trends analysis requested: {request.query}")
    try:
        return await manager.process_tech_trends_request(request)
    except Exception as e:
        logger.error(f"Tech trends analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repositories", response_model=RepoIntelResponse)
async def analyze_repositories(
    request: RepoIntelRequest,
    manager: AgentManager = Depends(get_agent_manager),
) -> RepoIntelResponse:
    """Analyze GitHub repositories using Specialist Agent."""
    logger.info(f"Repository analysis requested: {request.repositories}")
    try:
        return await manager.process_repo_intel_request(request)
    except Exception as e:
        logger.error(f"Repository analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/combined-analysis", response_model=CombinedAnalysisResponse)
async def combined_analysis(
    request: CombinedAnalysisRequest,
    manager: AgentManager = Depends(get_agent_manager),
) -> CombinedAnalysisResponse:
    """Perform combined tech trends and repository analysis."""
    logger.info(f"Combined analysis requested: {request.query}")
    try:
        return await manager.process_combined_analysis_request(request)
    except Exception as e:
        logger.error(f"Combined analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
