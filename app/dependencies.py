"""Shared dependencies for the application."""

from fastapi import HTTPException

from .services import AgentManager


def get_agent_manager() -> AgentManager:
    """Dependency to get the agent manager instance."""
    from .main import agent_manager

    if not agent_manager.initialized:
        raise HTTPException(status_code=503, detail="Agent manager not initialized")
    return agent_manager
