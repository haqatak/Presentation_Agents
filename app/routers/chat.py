"""Chat and assistant-related API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..models.requests import AssistantRouteRequest, GeneralChatRequest
from ..models.responses import AssistantRouteResponse, GeneralChatResponse
from ..services import AgentManager
from ..utils import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Chat"])


from ..dependencies import get_agent_manager


@router.post("/chat", response_model=GeneralChatResponse)
async def general_chat(
    request: GeneralChatRequest,
    manager: AgentManager = Depends(get_agent_manager),
) -> GeneralChatResponse:
    """Handle general AI chat for non-tech specific questions."""
    logger.info(f"General chat request: {request.message[:100]}...")
    try:
        # This will now be handled by the entry agent's process_general_chat
        if not manager.entry_agent:
            raise HTTPException(status_code=503, detail="Entry agent not available")
        return await manager.entry_agent.process_general_chat(request)
    except Exception as e:
        logger.error(f"General chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assistant", response_model=AssistantRouteResponse)
async def assistant_router(
    request: AssistantRouteRequest,
    manager: AgentManager = Depends(get_agent_manager),
):
    """Unified assistant endpoint that classifies and routes to trends or chat."""
    try:
        routed = await manager.route_user_intent(
            request.input,
            limit=request.limit or 10,
            include_hn=request.include_hn,
            include_brave=request.include_brave,
        )
        return AssistantRouteResponse(
            route=routed["route"],
            data=routed["data"],
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"Assistant routing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
