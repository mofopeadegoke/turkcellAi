import streamlit as st
import asyncio
import json
from openai import OpenAI
import os
from dotenv import load_dotenv
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

# --- Configuration ---
load_dotenv()  # Load environment variables from .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERVER_PATH = "../mcpsc/main.py" 

st.set_page_config(page_title="Turkcell AI Support", page_icon="🇹🇷")
st.title("🇹🇷 Turkcell AI Support Agent")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tools" not in st.session_state:
    st.session_state.tools = []

# --- 1. Automated Tool Discovery ---
async def fetch_mcp_tools():
    """Queries the MCP server and returns tools in OpenAI format."""
    server_params = StdioServerParameters(command="python", args=[SERVER_PATH])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = await session.list_tools()
            
            # Convert MCP schema to OpenAI function schema
            openai_formatted_tools = []
            for tool in mcp_tools.tools:
                openai_formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    }
                })
            return openai_formatted_tools

# Fetch tools once and store in session state
if not st.session_state.tools:
    with st.spinner("Connecting to Turkcell MCP Server..."):
        st.session_state.tools = asyncio.run(fetch_mcp_tools())
        st.success(f"Connected! {len(st.session_state.tools)} tools discovered.")

# --- 2. Tool Execution Logic ---
async def call_mcp_tool(tool_name, tool_args):
    server_params = StdioServerParameters(command="python", args=[SERVER_PATH])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_args)
            return result.content[0].text

for message in st.session_state.messages:
    if message.get("role") in ["user", "assistant"] and message.get("content"):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if prompt := st.chat_input("How can I help you today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=st.session_state.messages,
            tools=st.session_state.tools,
        )

        msg = response.choices[0].message
        if msg.tool_calls:
            st.session_state.messages.append(msg)
            
            for tool_call in msg.tool_calls:
                t_name = tool_call.function.name
                t_args = json.loads(tool_call.function.arguments)
                
                with st.status(f"Turkcell System: {t_name}...", expanded=False):
                    tool_result = asyncio.run(call_mcp_tool(t_name, t_args))
                    st.write("Response received from backend.")
                
                st.session_state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": t_name,
                    "content": tool_result
                })
            
            # Final response after tool execution
            final_res = client.chat.completions.create(
                model="gpt-4o",
                messages=st.session_state.messages
            )
            full_response = final_res.choices[0].message.content
        else:
            full_response = msg.content

        st.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})