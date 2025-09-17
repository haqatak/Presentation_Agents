"""Agent manager service for coordinating multiple agents."""

from datetime import datetime
from typing import Any

from ..agents import EntryAgent, SpecialistAgent
from ..agents.factory import AgentFactory
from ..models.requests import (
    CombinedAnalysisRequest,
    GeneralChatRequest,
    RepoIntelRequest,
    TechTrendsRequest,
)
from ..models.responses import (
    CombinedAnalysisResponse,
    RepoIntelResponse,
    TechTrendsResponse,
)
from ..utils import MCPClientManager, get_logger
from .a2a_service import A2AService

logger = get_logger(__name__)


class AgentManager:
    """Manager for coordinating multiple agents and their interactions."""

    def __init__(self) -> None:
        """Initialize the agent manager."""
        self.entry_agent: EntryAgent | None = None
        self.specialist_agent: SpecialistAgent | None = None
        self.a2a_service: A2AService | None = None
        self.mcp_manager: MCPClientManager | None = None
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize all agents and services."""
        try:
            logger.info("Initializing agent manager")
            self.mcp_manager = MCPClientManager()
            await self.mcp_manager.__aenter__()

            agent_factory = AgentFactory(self.mcp_manager)

            entry_agent_prompt = "You are a tech trend analysis expert."
            entry_pydantic_agent = agent_factory.create_agent(entry_agent_prompt)
            self.entry_agent = EntryAgent(entry_pydantic_agent, self.mcp_manager)

            specialist_agent_prompt = "You are a GitHub repository analysis expert."
            specialist_pydantic_agent = agent_factory.create_agent(
                specialist_agent_prompt
            )
            self.specialist_agent = SpecialistAgent(
                specialist_pydantic_agent, self.mcp_manager
            )

            self.a2a_service = A2AService()
            await self.a2a_service.start_server()
            if self.a2a_service:
                await self.a2a_service.register_agent(
                    "entry_agent", entry_pydantic_agent
                )
                await self.a2a_service.register_agent(
                    "specialist_agent", specialist_pydantic_agent
                )

            self.initialized = True
            logger.info("Agent manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize agent manager: {e}")
            raise

    async def receive_a2a_message(
        self, recipient: str, message_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Receive and dispatch an A2A message."""
        try:
            if recipient == "specialist_agent" and self.specialist_agent:
                return await self.specialist_agent.handle_delegation_from_entry(payload)
            return {"error": f"Unknown recipient or message type for {recipient}"}
        except Exception as e:
            logger.error(f"Error handling A2A message for {recipient}: {e}")
            return {"error": str(e)}

    async def shutdown(self) -> None:
        """Shutdown all agents and services."""
        try:
            logger.info("Shutting down agent manager")
            if self.a2a_service:
                await self.a2a_service.stop_server()
            if self.mcp_manager:
                await self.mcp_manager.__aexit__(None, None, None)
            self.initialized = False
            logger.info("Agent manager shut down successfully")
        except Exception as e:
            logger.error(f"Error during agent manager shutdown: {e}")

    async def process_tech_trends_request(
        self, request: TechTrendsRequest
    ) -> TechTrendsResponse:
        """Process a tech trends analysis request."""
        if not self.initialized or not self.entry_agent:
            raise RuntimeError("Agent manager not initialized")
        logger.info("Processing tech trends request")
        return await self.entry_agent.process_request(request)

    async def route_user_intent(
        self,
        input_text: str,
        *,
        limit: int = 10,
        include_hn: bool = True,
        include_brave: bool = True,
    ) -> dict[str, Any]:
        """Classify user input and route to trends or general chat."""
        if not self.initialized or not self.entry_agent:
            raise RuntimeError("Agent manager not initialized")

        classification = await self.entry_agent.classify_query(input_text)

        if classification == "TECH":
            trends_request = TechTrendsRequest(
                query=input_text,
                limit=limit,
                include_hn=include_hn,
                include_brave=include_brave,
            )
            data = await self.entry_agent.process_request(trends_request)
            return {"route": "trends", "data": data.dict()}
        else:
            chat_request = GeneralChatRequest(message=input_text)
            data = await self.entry_agent.process_general_chat(chat_request)
            return {"route": "chat", "data": data.dict()}

    async def process_repo_intel_request(
        self, request: RepoIntelRequest
    ) -> RepoIntelResponse:
        """Process a repository intelligence request."""
        if not self.initialized or not self.specialist_agent:
            raise RuntimeError("Agent manager not initialized")
        logger.info("Processing repository intelligence request")
        return await self.specialist_agent.process_request(request)

    async def process_combined_analysis_request(
        self, request: CombinedAnalysisRequest
    ) -> CombinedAnalysisResponse:
        """Process a combined analysis request."""
        if not self.initialized or not self.entry_agent or not self.specialist_agent:
            raise RuntimeError("Agent manager not initialized")
        logger.info("Processing combined analysis request")

        trends_request = TechTrendsRequest(
            query=request.query, limit=request.trend_limit
        )
        trends_response = await self.entry_agent.process_request(trends_request)

        repositories_to_analyze = []
        if request.auto_detect_repos:
            pass  # Placeholder for repo detection

        repo_intel_response = RepoIntelResponse(
            repositories=[], total_repos=0, analysis_timestamp=datetime.utcnow()
        )
        if repositories_to_analyze:
            repo_request = RepoIntelRequest(repositories=repositories_to_analyze)
            repo_intel_response = await self.specialist_agent.process_request(
                repo_request
            )

        return CombinedAnalysisResponse(
            query=request.query,
            trends=trends_response,
            repositories=repo_intel_response,
            correlation_analysis={
                "trending_technologies": [],
                "related_repositories": [],
                "correlation_score": 0.0,
                "key_insights": [],
            },
            recommendations=[],
            analysis_timestamp=datetime.utcnow(),
        )

    async def health_check(self) -> dict[str, Any]:
        """Perform health check for all agents and services."""
        health_status = {
            "agent_manager": {"initialized": self.initialized},
            "agents": {},
            "mcp_servers": {},
            "a2a_service": {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        if self.entry_agent:
            health_status["agents"]["entry_agent"] = await self.entry_agent.health_check()
        if self.specialist_agent:
            health_status["agents"][
                "specialist_agent"
            ] = await self.specialist_agent.health_check()
        if self.mcp_manager:
            health_status["mcp_servers"] = await self.mcp_manager.health_check_all()
        if self.a2a_service:
            health_status["a2a_service"] = await self.a2a_service.health_check()
        return health_status
