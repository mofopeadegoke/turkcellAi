import sys
import os
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from openai import OpenAI

class MCPProvider:
    name = "mcp"

    def __init__(self, server_path):
        self.server_path = server_path
        # We need an internal OpenAI client to make the decisions
        self.openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    async def ask(self, messages, customer_context=None):
        """
        The main brain loop:
        1. Connect to MCP Server
        2. Fetch available tools
        3. Send User Input + Tools to OpenAI
        4. If OpenAI calls a tool -> Execute it -> Send result back -> Get final answer
        """
        
        # 1. Setup Connection
        # Use 'sys.executable' to ensure we use the same python environment
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_path],
            env=os.environ.copy()
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 2. Get Tools from your Server
                mcp_tools = await session.list_tools()
                
                # Convert MCP tools to OpenAI format
                openai_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema
                        }
                    } for tool in mcp_tools.tools
                ]

                # 3. Ask OpenAI (Round 1)
                # We append the system instructions if they aren't there
                current_messages = list(messages)
                
                response = self.openai.chat.completions.create(
                    model="gpt-4o",
                    messages=current_messages,
                    tools=openai_tools,
                    tool_choice="auto" 
                )

                # 4. Handle Tool Calls
                msg = response.choices[0].message
                
                # If OpenAI wants to use a tool...
                if msg.tool_calls:
                    print(f"DEBUG: AI wants to call {len(msg.tool_calls)} tools.")
                    current_messages.append(msg) # Add the "intent" to history

                    for tool_call in msg.tool_calls:
                        t_name = tool_call.function.name
                        import json
                        t_args = json.loads(tool_call.function.arguments)
                        
                        print(f"DEBUG: Executing {t_name} with {t_args}")
                        
                        # EXECUTE THE TOOL via MCP
                        result = await session.call_tool(t_name, t_args)
                        tool_output = result.content[0].text

                        # Add the result to history
                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": t_name,
                            "content": tool_output
                        })

                    # 5. Ask OpenAI (Round 2) - Get Final Answer
                    final_response = self.openai.chat.completions.create(
                        model="gpt-4o",
                        messages=current_messages
                    )
                    return final_response.choices[0].message.content

                # If no tool was needed, just return the text
                return msg.content