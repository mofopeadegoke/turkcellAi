import asyncio
import logging
from .openai_provider import OpenAIProvider
from .mcp_provider import MCPProvider
from .safe_provider import SafeProvider

logger = logging.getLogger(__name__)


class IntelligenceClient:
    """
    Production AI Orchestrator

    Features:
    - Provider fallback
    - Retries
    - Timeout protection
    - Async safe for Twilio latency
    """

    def __init__(
        self,
        openai_api_key=None,
        mcp_server_path=None,
        primary="openai",
        timeout=7,
        retries=2,
    ):
        self.primary = primary
        self.timeout = timeout
        self.retries = retries

        self.openai = OpenAIProvider(openai_api_key) if openai_api_key else None
        self.mcp = MCPProvider(mcp_server_path) if mcp_server_path else None
        self.safe = SafeProvider()

    async def ask(self, messages, customer_context=None):

        providers = []

        if self.primary == "mcp":
            if self.mcp:
                providers.append(self.mcp)
            if self.openai:
                providers.append(self.openai)
        else:
            if self.openai:
                providers.append(self.openai)
            if self.mcp:
                providers.append(self.mcp)

        for provider in providers:
            for attempt in range(self.retries):
                try:
                    logger.info(f"Trying provider {provider.name} attempt {attempt+1}")

                    return await asyncio.wait_for(
                        provider.ask(messages, customer_context),
                        timeout=self.timeout,
                    )

                except Exception as e:
                    logger.warning(f"{provider.name} failed: {e}")

        logger.error("All providers failed — using safe fallback")
        return self.safe.ask(messages, customer_context)