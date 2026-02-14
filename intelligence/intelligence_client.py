import asyncio
import logging
from .openai_provider import OpenAIProvider
from .mcp_provider import MCPProvider
from .safe_provider import SafeProvider

# Set up logging to see what's happening in Railway logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelligenceClient:
    """
    The Brain Orchestrator
    
    It decides:
    1. Which AI provider to use (MCP with Tools vs. OpenAI Chat)
    2. Handles retries if one fails
    3. Formats simple text into complex message history
    """

    def __init__(
        self,
        openai_api_key=None,
        mcp_server_path=None,
        primary="mcp",  # Default to MCP so we use tools!
        timeout=10,     # Increased to 10s because tool calls take time
        retries=1,
    ):
        self.primary = primary
        self.timeout = timeout
        self.retries = retries

        # Initialize Providers
        self.openai = OpenAIProvider(openai_api_key) if openai_api_key else None
        
        # Only initialize MCP if we have a path
        if mcp_server_path:
            self.mcp = MCPProvider(mcp_server_path)
        else:
            self.mcp = None
            logger.warning("⚠️ No MCP Path provided. Tools will be disabled.")

        self.safe = SafeProvider()

    async def process_user_message(self, user_text, customer_context=None):
        """
        Helper to convert a simple string into the message format 
        that 'ask' expects. This is what main.py calls.
        """
        # Create a simple message history
        messages = [
            {"role": "user", "content": user_text}
        ]
        
        # Pass it to the main logic
        return await self.ask(messages, customer_context)

    async def ask(self, messages, customer_context=None):
        """
        The main logic loop: Try Primary -> Try Secondary -> Fallback
        """
        providers = []

        # 1. Determine Order
        # We almost ALWAYS want MCP first because it has the tools.
        if self.mcp:
            providers.append(self.mcp)
        
        # Add OpenAI as backup (it has no tools, but can chat)
        if self.openai:
            providers.append(self.openai)

        # 2. Try each provider
        for provider in providers:
            # We retry a few times in case of network blips
            for attempt in range(self.retries + 1):
                try:
                    logger.info(f"🧠 Thinking with {provider.name} (Attempt {attempt+1})...")

                    # Run with timeout protection
                    response = await asyncio.wait_for(
                        provider.ask(messages, customer_context),
                        timeout=self.timeout,
                    )
                    
                    if response:
                        return response

                except asyncio.TimeoutError:
                    logger.warning(f"⏳ {provider.name} timed out after {self.timeout}s")
                except Exception as e:
                    logger.error(f"❌ {provider.name} failed: {e}")
            
            logger.info(f"⚠️ {provider.name} failed all attempts. Switching to next provider.")

        # 3. Ultimate Fallback (if everything crashes)
        logger.critical("🚨 All AI providers failed. Using Safe Fallback.")
        return self.safe.ask(messages, customer_context)