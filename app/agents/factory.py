"""Factory for creating and configuring Pydantic-AI agents."""

import os
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from ..utils import MCPClientManager, get_logger, settings

logger = get_logger(__name__)

BRAVE_WEB_SEARCH_LIMIT = int(os.getenv("BRAVE_WEB_SEARCH_LIMIT", "20"))


class AgentFactory:
    """A factory for creating pre-configured Pydantic-AI agents."""

    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp_manager = mcp_manager
        if not os.getenv("OPENAI_API_KEY") and settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    def create_agent(self, system_prompt: str) -> Agent:
        """Creates a new Pydantic-AI Agent with all tools registered."""
        agent = Agent(
            model=OpenAIModel("gpt-4o"),
            system_prompt=system_prompt,
        )
        self._register_tools(agent)
        return agent

    def _register_tools(self, agent: Agent) -> None:
        """Registers all available MCP tools with the given agent."""

        @agent.tool
        async def search_brave(ctx: RunContext[Any], query: str, freshness: str = "pm"):
            """Search using Brave Search MCP server."""
            client = self.mcp_manager.get_client("brave_search")
            if not client:
                return {"error": "Brave Search MCP client not available"}
            try:
                return await client.call_tool(
                    "brave_web_search",
                    {"query": query, "freshness": freshness, "count": BRAVE_WEB_SEARCH_LIMIT},
                )
            except Exception as e:
                logger.error(f"Brave search failed: {e}")
                return {"error": "mcp_connection_failed", "details": str(e)}

        @agent.tool
        async def get_hacker_news_stories(
            ctx: RunContext[Any], story_type: str = "top", limit: int = 10
        ):
            """Get stories from Hacker News MCP server."""
            client = self.mcp_manager.get_client("hacker_news")
            if not client:
                return {"error": "Hacker News MCP client not available"}
            try:
                type_map = {"top": "topstories", "new": "newstories", "best": "beststories"}
                hn_story_type = type_map.get(story_type.lower(), story_type)
                return await client.call_tool(
                    "get_stories", {"story_type": hn_story_type, "limit": limit}
                )
            except Exception as e:
                logger.error(f"Hacker News fetch failed: {e}")
                return {"error": "mcp_connection_failed", "details": str(e)}

        @agent.tool
        async def search_github_repos(
            ctx: RunContext[Any], query: str, sort: str = "stars", limit: int = 10
        ):
            """Search GitHub repositories using GitHub MCP server."""
            client = self.mcp_manager.get_client("github")
            if not client:
                return {"error": "GitHub MCP client not available"}
            try:
                return await client.call_tool(
                    "search_repositories", {"query": query, "sort": sort, "per_page": limit}
                )
            except Exception as e:
                logger.error(f"GitHub search failed: {e}")
                return {"error": str(e)}

        @agent.tool
        async def get_github_repo_details(ctx: RunContext[Any], owner: str, repo: str):
            """Get detailed information about a GitHub repository."""
            client = self.mcp_manager.get_client("github")
            if not client:
                return {"error": "GitHub MCP client not available"}
            try:
                return await client.call_tool("get_repository", {"owner": owner, "repo": repo})
            except Exception as e:
                logger.error(f"GitHub repo details fetch failed: {e}")
                return {"error": str(e)}
