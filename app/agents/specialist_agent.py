"""Specialist Agent (Repo Intel) - Analyzes GitHub repositories and provides intelligence."""

from datetime import datetime
from typing import Any

from pydantic_ai import Agent

from ..models.requests import RepoIntelRequest
from ..models.responses import RepoIntelResponse
from ..models.schemas import GitHubRepository, RepoMetrics
from ..utils import get_logger

logger = get_logger(__name__)


class SpecialistAgent:
    """
    Service class for the Specialist Agent, focusing on GitHub intelligence.
    This class *uses* a Pydantic-AI Agent; it does not wrap it.
    """

    def __init__(self, agent: Agent, mcp_manager):
        self.agent = agent
        self.mcp_manager = mcp_manager
        self.agent_name = "specialist_agent"

    async def process_request(self, request: RepoIntelRequest) -> RepoIntelResponse:
        """Process a repository intelligence request."""
        logger.info(
            "Processing repository intelligence request",
            repositories=request.repositories,
            include_metrics=request.include_metrics,
        )

        repo_data = []
        try:
            for repo_name in request.repositories[:10]:
                repo_analysis = await self._analyze_repository(
                    repo_name, request.include_metrics
                )
                if repo_analysis:
                    repo_data.append(repo_analysis)

            insights = "No repositories could be analyzed."
            if repo_data:
                analysis_prompt = f"""
                Analyze the following GitHub repositories: {repo_data}
                Provide a comprehensive analysis of their health, community, and technology.
                """
                analysis_result = await self.agent.run(analysis_prompt)
                insights = self._extract_content(str(analysis_result))

            return RepoIntelResponse(
                repositories=repo_data,
                total_repos=len(repo_data),
                analysis_timestamp=datetime.utcnow(),
                insights=insights,
            )
        except Exception as e:
            logger.error(f"Error processing repository intelligence request: {e}")
            return RepoIntelResponse(
                repositories=[],
                total_repos=0,
                analysis_timestamp=datetime.utcnow(),
                insights=f"An error occurred: {e}",
            )

    async def _analyze_repository(
        self, repo_name: str, include_metrics: bool
    ) -> GitHubRepository | None:
        """Analyze a single GitHub repository."""
        try:
            if "/" not in repo_name:
                logger.warning(f"Invalid repository name format: {repo_name}")
                return None

            owner, repo = repo_name.split("/", 1)
            details_result = await self.agent.run(
                f"Get GitHub repository details for {owner}/{repo}"
            )
            repo_details = details_result.data
            if not repo_details:
                return None

            metrics = repo_details.get("metrics", {})
            return GitHubRepository(
                name=repo,
                full_name=repo_name,
                owner=owner,
                description=repo_details.get("description", ""),
                url=repo_details.get("html_url", f"https://github.com/{repo_name}"),
                homepage=repo_details.get("homepage"),
                created_at=repo_details.get("created_at"),
                updated_at=repo_details.get("updated_at"),
                pushed_at=repo_details.get("pushed_at"),
                metrics=RepoMetrics(
                    stars=metrics.get("stars", 0),
                    forks=metrics.get("forks", 0),
                    watchers=metrics.get("watchers", 0),
                    open_issues=metrics.get("open_issues", 0),
                    size=metrics.get("size", 0),
                    language=metrics.get("language"),
                    default_branch=repo_details.get("default_branch", "main"),
                ),
                topics=repo_details.get("topics", []),
                license=repo_details.get("license", {}).get("name"),
                is_fork=repo_details.get("fork", False),
                archived=repo_details.get("archived", False),
            )
        except Exception as e:
            logger.error(f"Failed to analyze repository {repo_name}: {e}")
            return None

    async def health_check(self) -> dict[str, str]:
        """Perform health check for the agent."""
        status = "healthy"
        details = f"Agent {self.agent_name} is operational"
        if not self.mcp_manager:
            status = "degraded"
            details = "MCP manager not initialized"
        return {
            "status": status,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _extract_content(self, agent_result_str: str) -> str:
        """Extract clean content from agent result string."""
        if "AgentRunResult(output=" in agent_result_str:
            start = agent_result_str.find("output='") + 8
            if start > 7:
                end = agent_result_str.rfind("')")
                if end > start:
                    return agent_result_str[start:end].replace("\\'", "'")
        return agent_result_str

    async def handle_delegation_from_entry(
        self,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle delegation request from Entry Agent."""
        payload = message.get("payload", {})
        repositories = payload.get("repositories", [])

        request = RepoIntelRequest(repositories=repositories)
        result = await self.process_request(request)

        # This method would typically send a response back via A2A,
        # but for now, we just return the result.
        return result.dict()
