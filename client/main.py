import asyncio
from openai import OpenAI
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
server_path = os.path.join(base_dir, "..", "mcpsc", "main.py")


# 1. Initialize OpenAI
ai_client = OpenAI(api_key="your_openai_key")

async def run_agent():
    # 2. Connect to your MCP Server    
    server_params = StdioServerParameters(
        command="python", 
        args=[server_path]
    )
        
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            
            # 3. Get list of tools from your server
            mcp_tools = await session.list_tools()
            
            # 4. Convert MCP tools to OpenAI tool format
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                }
                for tool in mcp_tools.tools
            ]

            # 5. The Chat Loop
            messages = [{"role": "user", "content": "Can you check my balance? My number is +905321112233"}]
            
            response = ai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=openai_tools
            )

            # (Logic here to handle tool_calls and return results to AI)
            print(response.choices[0].message.content)

if __name__ == "__main__":
    asyncio.run(run_agent())

    