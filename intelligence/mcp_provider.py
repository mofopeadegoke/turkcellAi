import sys
import os
import json
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from openai import OpenAI

# --- THE CRITICAL FIX: The "Personality" ---
# This tells the MCP Brain that it works for Turkcell and MUST use tools.
MCP_SYSTEM_PROMPT = """
You are the advanced Turkcell AI Support Agent. 
Your goal is to solve customer problems efficiently using real-time data.

### 🛠️ TOOL USAGE PROTOCOL
1. **Analyze First:** When you receive a message, immediately scan your available tools.
2. **Don't Guess:** If the user asks for ANY information that might be in a database (balances, package details, network status, store locations, prices), you **MUST** use a tool.
3. **Be Proactive:** If a tool requires a phone number and you have it in the context, use it automatically.
4. **Tool Variety:** Do not limit yourself. If you have tools for network checks, selling packages, or troubleshooting, use them when appropriate.

### 🎨 FORMATTING RULES
- **Bolding:** Use single asterisks for emphasis (e.g., *20 GB*), NOT double asterisks.
- **Brevity:** Keep responses concise. You are likely speaking on WhatsApp or Voice.
- **Language:** Detect the user's language and respond in the same language.

### ⚠️ ERROR HANDLING & FALLBACKS
- **If a tool fails** (returns an error or empty result):
  - Do NOT make up numbers.
  - Apologize and say: "I am having trouble accessing that data right now."
  - Suggest an alternative (e.g., "You can dial *100# to check your balance.").
- **If no tool matches:** Only then should you answer using your general knowledge.

### 🛡️ SECURITY
- Never reveal customer data to the wrong phone number.
- Identify scams (e.g., high prices for SIMs) and warn the user.
"""
class MCPProvider:
    name = "mcp"

    def __init__(self, server_path):
        self.server_path = server_path
        # We use a separate OpenAI client here to drive the decision making
        self.openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    async def ask(self, messages, customer_context=None):
        print(f"🔌 MCP Provider: Connecting to {self.server_path}")
        
        # 1. Setup Connection to the Tool Server
        # We use sys.executable to ensure we use the same Python environment
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_path],
            env=os.environ.copy()
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 2. Get Tools (The "Hands")
                mcp_tools = await session.list_tools()
                print(f"🛠️  MCP Tools Found: {[t.name for t in mcp_tools.tools]}")
                
                # Convert to OpenAI Format
                openai_tools = [{
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                } for tool in mcp_tools.tools]

                # 3. Prepare the Prompt (The "Brain")
                # We inject the System Prompt at the very start!
                current_messages = [{"role": "system", "content": MCP_SYSTEM_PROMPT}]
                
                # Add context if we have it (e.g., Name, Language)
                if customer_context:
                    context_str = f"Customer Context: {json.dumps(customer_context)}"
                    current_messages.append({"role": "system", "content": context_str})
                
                # Add the user's actual conversation history
                current_messages += messages

                # 4. Ask OpenAI (Round 1)
                print("🧠 MCP Brain: Thinking...")
                response = self.openai.chat.completions.create(
                    model="gpt-4o",
                    messages=current_messages,
                    tools=openai_tools,
                    tool_choice="auto"  # The System Prompt forces this to happen
                )

                msg = response.choices[0].message
                
                # 5. DID IT DECIDE TO USE A TOOL?
                if msg.tool_calls:
                    print(f"🚨 TOOL DETECTED: The AI wants to use {len(msg.tool_calls)} tools!")
                    current_messages.append(msg) # Add the "intent" to history

                    for tool_call in msg.tool_calls:
                        t_name = tool_call.function.name
                        t_args = json.loads(tool_call.function.arguments)
                        
                        print(f"🏃 Executing Tool: {t_name} with args {t_args}")
                        
                        # --- EXECUTE THE TOOL ---
                        # This runs the code in mcpsc/main.py
                        result = await session.call_tool(t_name, t_args)
                        
                        # Get the text result
                        tool_output = result.content[0].text
                        print(f"✅ Tool Result: {tool_output[:100]}...") # Print first 100 chars

                        # Add the result to history so AI can read it
                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": t_name,
                            "content": tool_output
                        })

                    # 6. Ask OpenAI (Round 2) - Interpret the Data
                    print("🧠 MCP Brain: Finalizing answer with tool data...")
                    final_response = self.openai.chat.completions.create(
                        model="gpt-4o",
                        messages=current_messages
                    )
                    return final_response.choices[0].message.content
                
                else:
                    print("🤷 MCP Brain: Decided NOT to use tools.")
                    return msg.content